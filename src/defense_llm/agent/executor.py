"""LLM-driven Executor: tool dispatch + schema validation + response template (UF-031)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from ..security.rbac import check_access
from ..rag.citation import package_citations
from ..audit.logger import AuditLogger
from .tool_schemas import validate_tool_call, get_tool_definitions_for_llm
from .decision_support import (
    coa_generate as _coa_generate_fn,
    ipb_summary as _ipb_summary_fn,
    roe_check as _roe_check_fn,
    fires_plan as _fires_plan_fn,
)
from .commander_interface import compose_decision_support_response as _compose_dsp
from .script_tools import (
    create_script,
    create_batch_script,
    execute_batch_script,
    save_results_csv,
    DEFAULT_TIMEOUT_SECONDS,
)

E_AUTH = "E_AUTH"
E_VALIDATION = "E_VALIDATION"
E_INTERNAL = "E_INTERNAL"
E_LOOP_LIMIT = "E_LOOP_LIMIT"

_CLEARANCE_ORDER = ["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]

# Sentinel token: LLM must emit this exact string when no relevant docs found
_NO_DOCS_SENTINEL = "[NO_RELEVANT_DOCS]"

_AGENT_SYSTEM_PROMPT = (
    "당신은 방산 도메인 지식 보조 AI 에이전트입니다. "
    "제공된 도구를 사용하여 단계적으로 질문에 답하십시오. "
    "정보 검색 순서: (1) search_docs로 내부 지식 베이스를 먼저 탐색하십시오. "
    "(2) 내부 문서에 관련 정보가 없을 때만 web_search를 사용하십시오 (web_search 도구가 제공된 경우에 한함). "
    "근거 문서가 없거나 답변이 불가능하면 반드시 '[NO_RELEVANT_DOCS]' 토큰만 출력하십시오. "
    "스크립트 실행 결과는 CSV로 저장하고 결과 경로를 보고하십시오."
)

_PIPELINE_SYSTEM_PROMPT = (
    "당신은 방산 도메인 지식 보조 AI입니다. "
    "제공된 근거 자료에 질문에 대한 명확한 답이 없다면 "
    "반드시 '[NO_RELEVANT_DOCS]' 토큰만 반환하십시오. "
    "답변이 가능하다면 검색된 문서 내용만을 바탕으로 한국어로 답변하고 "
    "출처 표기는 생략하십시오."
)


def _normalize_id(s: str) -> str:
    """Strip hyphens and spaces, uppercase — for fuzzy platform/weapon ID matching."""
    return re.sub(r"[-\s]", "", s.upper())


class Executor:
    """Executes a tool plan produced by the Planner (UF-031).

    Args:
        llm_adapter: An AbstractLLMAdapter instance for text generation.
        index: DocumentIndex instance for RAG search.
        db_path: Path to SQLite DB for structured queries.
        audit_logger: AuditLogger instance.
        model_version: Model version string for response metadata.
        index_version: Index version string for response metadata.
        db_schema_version: DB schema version string.
    """

    def __init__(
        self,
        llm_adapter,
        index,
        db_path: str,
        audit_logger: AuditLogger,
        model_version: str = "qwen2.5-1.5b-instruct",
        index_version: str = "idx-00000000-0000",
        db_schema_version: str = "schema-v1",
        index_path: Optional[str] = None,
        agent_mode: bool = False,
        max_agent_turns: int = 10,
        script_tools_enabled: bool = False,
        online_mode_enabled: bool = False,
    ) -> None:
        self._llm = llm_adapter
        self._index = index
        self._db_path = db_path
        self._audit = audit_logger
        self._model_version = model_version
        self._index_version = index_version
        self._db_schema_version = db_schema_version
        self._index_path = index_path
        self._agent_mode = agent_mode
        self._max_agent_turns = max_agent_turns
        self._script_tools_enabled = script_tools_enabled
        self._online_mode_enabled = online_mode_enabled

    def execute(
        self,
        tool_plan: List[dict],
        user_context: dict,
        request_id: Optional[str] = None,
        query: Optional[str] = None,
        agent_mode: Optional[bool] = None,
        max_agent_turns: Optional[int] = None,
        battle_context=None,
    ) -> dict:
        """Execute a tool plan (pipeline mode) or run the agent loop.

        Args:
            tool_plan: List of { tool: str, params: dict } dicts.
                       Used in pipeline mode; ignored in agent mode.
            user_context: { role: str, clearance: str, user_id: str }.
            request_id: Optional pre-assigned request UUID.
            query: Raw user query string. Required for agent mode.
            agent_mode: If True, run the ReAct agent loop instead of the
                        static plan. If None, uses the instance default
                        (self._agent_mode).
            battle_context: Optional BattleSituationContext instance.
                            When provided (agent mode), its to_prompt_text()
                            is prepended to the user turn for full situational
                            awareness. Also enables the threat_assess tool.

        Returns:
            Standard response schema dict.
        """
        use_agent = self._agent_mode if agent_mode is None else agent_mode
        request_id = request_id or str(uuid.uuid4())
        error_code: Optional[str] = None
        citations: List[dict] = []
        answer_text = ""
        tool_call_log: List[dict] = []

        # Derive query_str for audit log
        if use_agent and query:
            query_str = query
        else:
            query_str = str(tool_plan)

        try:
            if use_agent and query:
                answer_text, citations, error_code, tool_call_log = self._run_agent_loop(
                    query, user_context,
                    max_turns=max_agent_turns,
                    battle_context=battle_context,
                )
            else:
                answer_text, citations, error_code = self._run_plan(
                    tool_plan, user_context
                )
        except PermissionError as e:
            error_code = E_AUTH
            answer_text = str(e)
        except ValueError as e:
            error_code = E_VALIDATION
            answer_text = str(e)
        except Exception as e:
            error_code = E_INTERNAL
            answer_text = f"내부 오류가 발생했습니다: {e}"

        response = self._build_response(
            request_id=request_id,
            answer=answer_text,
            citations=citations,
            security_label=user_context.get("clearance", "PUBLIC"),
            error_code=error_code,
            tool_call_log=tool_call_log if tool_call_log else None,
        )

        self._audit.write(
            request_id=request_id,
            user_id=user_context.get("user_id", "unknown"),
            query=query_str,
            model_version=self._model_version,
            index_version=self._index_version,
            citations=citations,
            response_hash=response["hash"],
            error_code=error_code,
        )

        return response

    # ------------------------------------------------------------------
    # Agent loop (ReAct / Function-Calling)
    # ------------------------------------------------------------------

    def _run_agent_loop(
        self,
        query: str,
        user_context: dict,
        max_turns: Optional[int] = None,
        battle_context=None,
    ):
        """ReAct agent loop: Observe → Think → Act until done or max_turns exceeded.

        The LLM drives tool selection. Each iteration:
          1. LLM receives messages + tool definitions → may return tool_calls
          2. Each tool_call is validated + security-checked → dispatched
          3. Tool result appended as "tool" role message
          4. Loop exits when LLM returns plain content (no tool_calls)
             or max_agent_turns is reached.

        Args:
            battle_context: Optional BattleSituationContext. When provided,
                its to_prompt_text() is prepended to the user turn and
                the threat_assess tool is added to available tools.

        Returns:
            Tuple (answer, citations, error_code, tool_call_log)
        """
        # Determine available tools
        available_tools = [
            "search_docs", "query_structured_db",
            "generate_answer", "format_response", "security_refusal",
        ]
        # Phase 3 decision support tools are activated when battle_context is supplied.
        # Order follows the recommended usage sequence:
        #   threat_assess → ipb_summary → coa_generate → roe_check → fires_plan
        if battle_context is not None:
            battle_tools = [
                "threat_assess", "ipb_summary",
                "coa_generate", "roe_check", "fires_plan",
                "decision_support_composite",   # Phase 4: single-call composite chain
            ]
            available_tools = battle_tools + available_tools
        # web_search is only offered to the LLM when the server has
        # online access enabled.  This is a server-level policy decision,
        # not an LLM decision — the LLM learns it can use web_search
        # purely from the tool being present in tool_defs.
        if self._online_mode_enabled:
            available_tools.append("web_search")
        if self._script_tools_enabled:
            available_tools += [
                "create_script", "create_batch_script",
                "execute_batch_script", "save_results_csv",
            ]

        tool_defs = get_tool_definitions_for_llm(available_tools)

        # Build user turn — prepend battle situation context when provided
        if battle_context is not None:
            user_content = (
                f"{battle_context.to_prompt_text()}\n\n질의: {query}"
            )
        else:
            user_content = query

        messages: List[dict] = [
            {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        collected_chunks: List[dict] = []
        db_results: List[dict] = []
        answer = ""
        tool_call_log: List[dict] = []

        effective_turns = max_turns if max_turns is not None else self._max_agent_turns

        for _turn in range(effective_turns):
            resp = self._llm.chat(messages, tools=tool_defs)
            tool_calls = resp.get("tool_calls")

            if not tool_calls:
                # LLM decided to respond with text — extract final answer
                answer = (resp.get("content") or "").strip()
                break

            # Append assistant message (with tool_calls) to conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": resp.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            # Dispatch each tool call
            for tc in tool_calls:
                tc_id = tc.get("id", f"call_{_turn}")
                tool_name = tc["function"]["name"]
                arguments = tc["function"]["arguments"]

                validation = validate_tool_call(tool_name, arguments)
                if not validation["valid"]:
                    tool_result: dict = {
                        "error": f"{E_VALIDATION}: {validation['errors']}"
                    }
                else:
                    try:
                        tool_result = self._dispatch_tool(
                            tool_name, arguments, user_context,
                            collected_chunks, db_results,
                        )
                    except PermissionError as exc:
                        tool_result = {"error": str(exc)}
                    except Exception as exc:
                        tool_result = {"error": f"{E_INTERNAL}: {exc}"}

                # Accumulate tool call trace for web display
                tool_call_log.append({
                    "turn": _turn,
                    "tool_name": tool_name,
                    "args_summary": str(arguments)[:200],
                    "result_summary": str(tool_result)[:200],
                    "error": tool_result.get("error"),
                })

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
        else:
            # Max turns exceeded
            answer = f"[에이전트 루프 최대 턴({effective_turns}) 초과]"
            citations_out = package_citations(collected_chunks) if collected_chunks else []
            return answer, citations_out, E_LOOP_LIMIT, tool_call_log

        # Sentinel-based "no docs" handling
        if answer == _NO_DOCS_SENTINEL:
            return "질의와 관련된 근거 문서를 찾을 수 없습니다.", [], None, tool_call_log

        citations_out = package_citations(collected_chunks) if collected_chunks else []
        return answer, citations_out, None, tool_call_log

    def _dispatch_tool(
        self,
        tool_name: str,
        arguments: dict,
        user_context: dict,
        collected_chunks: List[dict],
        db_results: List[dict],
    ) -> dict:
        """Dispatch a validated tool call to its handler.

        Mutates *collected_chunks* and *db_results* in-place when applicable.
        Raises PermissionError for security violations.

        Returns:
            Serialisable result dict passed back to the LLM as a tool message.
        """
        if tool_name == "security_refusal":
            raise PermissionError(
                f"{E_AUTH}: {arguments.get('reason', 'Access restricted.')}"
            )

        # ── Phase 2/3 battle situation tools ──────────────────────────────
        if tool_name == "threat_assess":
            return self._threat_assess(arguments)

        if tool_name == "ipb_summary":
            return _ipb_summary_fn(arguments, self._llm)

        if tool_name == "coa_generate":
            return _coa_generate_fn(arguments, self._llm)

        if tool_name == "roe_check":
            return _roe_check_fn(arguments)

        if tool_name == "fires_plan":
            return _fires_plan_fn(arguments)

        if tool_name == "decision_support_composite":
            # Phase 4: full decision support chain via commander_interface
            return _compose_dsp(arguments, self._llm, self._threat_assess)
        # ──────────────────────────────────────────────────────────────────

        if tool_name == "search_docs":
            # NOTE: RBAC check disabled — re-enable when JWT auth layer is added
            # access = check_access(
            #     user=user_context,
            #     resource_security_labels=arguments.get(
            #         "security_label_filter", ["PUBLIC"]
            #     ),
            # )
            # if not access["allowed"]:
            #     return {"error": f"{E_AUTH}: {access['reason']}"}

            results = self._index.search(
                query=arguments["query"],
                top_k=arguments.get("top_k", 5),
                field_filter=arguments.get("field_filter"),
                security_label_filter=arguments.get("security_label_filter"),
            )
            collected_chunks.extend(results)
            return {
                "chunks_found": len(results),
                "top_doc_ids": [r.get("doc_id") for r in results[:3]],
            }

        if tool_name == "web_search":
            # Server-level gate: web_search is only reachable when
            # online_mode_enabled=True.  If the LLM somehow calls this
            # tool when it was not advertised, block it here.
            if not self._online_mode_enabled:
                return {"error": f"{E_AUTH}: web_search is disabled in offline mode."}
            web_params = {
                "query": arguments["query"],
                "top_k": arguments.get("top_k", 3),
            }
            results = self._fallback_web_search(web_params)
            collected_chunks.extend(results)
            return {
                "chunks_found": len(results),
                "top_doc_ids": [r.get("doc_id") for r in results[:3]],
                "source": "web",
            }

        if tool_name == "query_structured_db":
            rows = self._query_db(arguments)
            db_results.extend(rows)
            return {"rows_found": len(rows), "rows": rows}

        if tool_name in ("generate_answer", "format_response"):
            return {"status": "acknowledged"}

        # Script execution tools (require script_tools_enabled)
        if not self._script_tools_enabled:
            return {"error": f"{E_AUTH}: Script tools are disabled."}

        if tool_name == "create_script":
            result = create_script(
                script_path=arguments["script_path"],
                script_content=arguments["script_content"],
                overwrite=arguments.get("overwrite", False),
            )
            return result

        if tool_name == "create_batch_script":
            result = create_batch_script(
                batch_path=arguments["batch_path"],
                script_path=arguments["script_path"],
                python_exe=arguments.get("python_exe", "python"),
                extra_args=arguments.get("extra_args"),
            )
            return result

        if tool_name == "execute_batch_script":
            result = execute_batch_script(
                batch_path=arguments["batch_path"],
                timeout_seconds=arguments.get(
                    "timeout_seconds", DEFAULT_TIMEOUT_SECONDS
                ),
                capture_output=arguments.get("capture_output", True),
            )
            # Audit every script execution separately
            exec_hash = hashlib.sha256(
                json.dumps(result, ensure_ascii=False).encode()
            ).hexdigest()
            self._audit.write(
                request_id=str(uuid.uuid4()),
                user_id=user_context.get("user_id", "unknown"),
                query=f"execute_batch_script:{arguments.get('batch_path', '')}",
                model_version=self._model_version,
                index_version=self._index_version,
                citations=[],
                response_hash=exec_hash,
                error_code=None if result.get("success") else E_INTERNAL,
            )
            return result

        if tool_name == "save_results_csv":
            result = save_results_csv(
                data=arguments["data"],
                csv_path=arguments["csv_path"],
                encoding=arguments.get("encoding", "utf-8-sig"),
            )
            return result

        return {"error": f"Unknown tool: '{tool_name}'"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _threat_assess(self, arguments: dict) -> dict:
        """Rule-based threat assessment handler for the threat_assess tool.

        Computes a normalised threat_score (0.0–1.0) from:
          - Base weight by threat type
          - Movement modifier
          - Count scaling (log-saturating)
          - Confidence weighting
        Then maps the score to a qualitative threat_level and generates
        recommended_actions that respect the supplied ROE level.

        Returns a serialisable dict passed back to the LLM as a tool message.
        """
        # ── Base score by threat type ──────────────────────────────────────
        _TYPE_BASE: Dict[str, float] = {
            "MISSILE":   0.95,
            "AIR":       0.85,
            "ARMOR":     0.80,
            "NAVAL":     0.70,
            "MIXED":     0.75,
            "DRONE":     0.60,
            "INFANTRY":  0.50,
            "CYBER":     0.55,
        }
        threat_type = str(arguments.get("threat_type", "MIXED")).upper()
        base = _TYPE_BASE.get(threat_type, 0.60)

        # ── Movement modifier ──────────────────────────────────────────────
        _MOVE_MOD: Dict[str, float] = {
            "ADVANCING":  0.25,
            "FLANKING":   0.20,
            "STATIONARY": 0.00,
            "RETREATING": -0.20,
            "UNKNOWN":    0.05,
        }
        movement = str(arguments.get("movement", "UNKNOWN")).upper()
        move_mod = _MOVE_MOD.get(movement, 0.05)

        # ── Count scaling (log-saturating: +0 at 1, +0.2 at ~55) ──────────
        import math
        count = max(1, int(arguments.get("count", 1)))
        count_mod = min(0.20, 0.20 * math.log10(count) / math.log10(55))

        # ── Confidence weighting ───────────────────────────────────────────
        confidence = float(arguments.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        # Low-confidence threats still matter but score is tempered
        raw_score = (base + move_mod + count_mod) * (0.5 + 0.5 * confidence)
        threat_score = round(max(0.0, min(1.0, raw_score)), 3)

        # ── Qualitative level ──────────────────────────────────────────────
        if threat_score >= 0.80:
            threat_level = "CRITICAL"
        elif threat_score >= 0.65:
            threat_level = "HIGH"
        elif threat_score >= 0.45:
            threat_level = "MEDIUM"
        elif threat_score >= 0.25:
            threat_level = "LOW"
        else:
            threat_level = "MINIMAL"

        # ── Threat summary ─────────────────────────────────────────────────
        threat_summary = (
            f"{threat_type} 위협 {count}개 ({movement}), "
            f"신뢰도 {confidence:.0%} → 위협수준 {threat_level} "
            f"(점수: {threat_score:.3f})"
        )

        # ── ROE-aware recommended actions ──────────────────────────────────
        roe_level = str(arguments.get("roe_level", "RETURN_FIRE")).upper()
        available_fires: List[str] = list(arguments.get("available_fires", []))
        friendly_unit_type = str(arguments.get("friendly_unit_type", "")).upper()

        _ROE_LABEL: Dict[str, str] = {
            "HOLD":          "교전 금지 — 회피·방어 기동만 허용",
            "RETURN_FIRE":   "반격 허용 — 선제 공격 금지",
            "FIRE_AT_WILL":  "자유 교전 — 적 식별 후 즉시 교전 가능",
            "WEAPONS_FREE":  "완전 개방 — 무제한 화력 사용 가능",
        }
        label = _ROE_LABEL.get(roe_level)
        roe_constraint = f"{roe_level}: {label}" if label else f"ROE '{roe_level}' 미정의"

        actions: List[str] = []

        if threat_level == "CRITICAL":
            if roe_level in ("FIRE_AT_WILL", "WEAPONS_FREE"):
                actions.append("즉각 최우선 화력 집중 — 전 가용 화력 투입")
            elif roe_level == "RETURN_FIRE":
                actions.append("적 선제 공격 즉시 반격 준비 — 화력 대기 태세 유지")
            else:
                actions.append("즉시 방어 진지 강화 및 예비대 전방 이동")
            actions.append("상급부대 긴급 보고 및 증원 요청")
            actions.append("비전투원 구역 즉시 소개")

        elif threat_level == "HIGH":
            if roe_level not in ("HOLD",):
                actions.append("직접 관측 사격 (정밀 타격) 준비 — 선별 화력 운용")
            actions.append("기동 방어 포지션으로 전환 — 측면 노출 최소화")
            actions.append("정보 갱신 요청 — 2제대 확인 필요")

        elif threat_level == "MEDIUM":
            actions.append("경계 강화 및 관측 전초 전진 배치")
            actions.append("예비 화력 계획 수립 (H 마이너스 계획)")
            if confidence < 0.6:
                actions.append("추가 정찰 자산 투입 — 위협 정보 갱신")

        else:  # LOW / MINIMAL
            actions.append("지속 감시 유지 — 상황 변화 모니터링")
            actions.append("현 방어 태세 유지, 전투력 보존 우선")

        # Fires-specific recommendation
        if available_fires and roe_level not in ("HOLD",):
            fires_str = ", ".join(available_fires[:3])
            actions.append(f"가용 화력 ({fires_str}) 표적 우선순위 지정 및 사격 제원 준비")

        # Unit-type specific note
        if friendly_unit_type in ("MECH_INF", "ARMOR") and threat_type == "ARMOR":
            actions.append("기갑 대 기갑 직접 교전 회피 — AT 미사일·공중 화력 우선 운용")

        confidence_note = (
            "정보 신뢰도가 낮습니다 — 위협 수준 상향 대비 필요" if confidence < 0.5
            else "정보 신뢰도 양호 — 평가 결과 신뢰 가능"
        )

        return {
            "threat_level": threat_level,
            "threat_score": threat_score,
            "threat_summary": threat_summary,
            "roe_constraint": roe_constraint,
            "recommended_actions": actions,
            "confidence_note": confidence_note,
        }

    def _run_plan(
        self, tool_plan: List[dict], user_context: dict
    ):
        """Run each tool in the plan. Returns (answer, citations, error_code)."""
        collected_chunks: List[dict] = []
        db_results: List[dict] = []
        error_code = None

        for step in tool_plan:
            tool = step.get("tool", "")
            params = step.get("params", {})

            # Schema validation
            validation = validate_tool_call(tool, params)
            if not validation["valid"]:
                raise ValueError(
                    f"{E_VALIDATION}: Tool '{tool}' schema error: {validation['errors']}"
                )

            if tool == "security_refusal":
                raise PermissionError(
                    f"{E_AUTH}: {params.get('reason', 'Access restricted.')}"
                )

            elif tool == "search_docs":
                # NOTE: RBAC check disabled — re-enable when JWT auth layer is added
                # access = check_access(
                #     user=user_context,
                #     resource_security_labels=params.get("security_label_filter", ["PUBLIC"]),
                # )
                # if not access["allowed"]:
                #     raise PermissionError(f"{E_AUTH}: {access['reason']}")

                query = params["query"]
                
                results = self._index.search(
                    query=query,
                    top_k=params.get("top_k", 5),
                    field_filter=params.get("field_filter"),
                    security_label_filter=params.get("security_label_filter"),
                )
                
                # Dynamic Web Search Fallback (pipeline mode only).
                # Requires both the per-request online_mode flag AND the
                # server-level online_mode_enabled=True gate.
                if params.get("online_mode") and self._online_mode_enabled:
                    web_results = self._fallback_web_search(params)
                    if web_results:
                        results = web_results
                    
                collected_chunks.extend(results)

            elif tool == "query_structured_db":
                db_results = self._query_db(params)

            elif tool in ("generate_answer", "format_response"):
                pass  # handled below after all data collection

        # Package citations
        if collected_chunks:
            citations = package_citations(collected_chunks)
        else:
            citations = []

        # Generate answer via LLM
        context_text = self._build_context(collected_chunks, db_results)
        
        # Extract query text from plan
        query_text = ""
        for step in tool_plan:
            query_text = query_text or step.get("params", {}).get("query", "")

        if not context_text and not error_code:
            answer = "검색 결과가 없습니다. 질의와 관련된 문서가 색인되지 않았거나 접근 권한이 없습니다."
        else:
            messages = [
                {"role": "system", "content": _PIPELINE_SYSTEM_PROMPT},
                {"role": "user", "content": f"질문: {query_text}\n\n근거 자료:\n{context_text}"},
            ]
            llm_resp = self._llm.chat(messages)
            answer = llm_resp.get("content", "").strip()

            # Sentinel-based citation clearing (exact match only — prevents false positives)
            if answer == _NO_DOCS_SENTINEL:
                citations = []
                answer = "질의와 관련된 근거 문서를 찾을 수 없습니다."

            # UF-023: Response Translation Processor
            is_korean_requested = "한글" in query_text or "한국어" in query_text
            if is_korean_requested and answer and citations:
                trans_messages = [
                    {"role": "system", "content": "당신은 전문 번역가입니다. 주어진 영문 응답을 자연스러운 한국어로 번역하십시오. 결과만 말하십시오."},
                    {"role": "user", "content": answer},
                ]
                trans_resp = self._llm.chat(trans_messages)
                answer = trans_resp.get("content", answer)

        return answer, citations, error_code

    def _fallback_web_search(self, params: dict) -> List[dict]:
        """Dynamic Web Search Fallback — fetches public web results, chunks them,
        adds to the live index, and returns a ranked search over the updated index.

        Called by:
          - Agent mode:    _dispatch_tool("web_search", ...) when online_mode_enabled=True
          - Pipeline mode: search_docs with online_mode=True AND online_mode_enabled=True

        Args:
            params: dict with keys:
                query (str, required): search query
                top_k (int, optional): max results to return (default 3)
                field_filter (list, optional): domain field whitelist
                security_label_filter (list, optional): security label whitelist

        Fixes applied (2026-03-26):
          - BUG-1: chunk_document() called with version= (was doc_rev=, TypeError)
          - BUG-2: removed redundant c.doc_id reassignment (already set by chunk_document)
          - BUG-3: source_uri=url passed to chunk_document for citation traceability
          - BUG-4: removed unused imports (requests, BeautifulSoup)
          - BUG-5: removed redundant re-imports of json/os/re/hashlib (top-level)
          - BUG-6: max_results respects top_k param
        """
        import datetime
        from duckduckgo_search import DDGS
        from ..rag.chunker import chunk_document
        from ..knowledge.document_meta import register_document

        query = params.get("query", "")
        if not query:
            return []

        top_k = params.get("top_k", 3)
        # Fetch at least as many web results as top_k (minimum 2 for relevance)
        fetch_count = max(2, top_k)

        try:
            ddgs = DDGS()
            search_results = list(ddgs.text(query, max_results=fetch_count))

            added_any = False
            for result in search_results:
                url = result.get("href")
                title = result.get("title", "")
                body_text = result.get("body", "")
                if not url or not body_text:
                    continue
                try:
                    text = f"{title}\n\n{body_text}"
                    doc_id = f"WEB-{abs(hash(url)) % 100000}"

                    # Determine domain field: prefer explicit filter, else ask LLM
                    ff = params.get("field_filter")
                    if ff:
                        field = ff[0]
                    else:
                        clf_msg = [
                            {
                                "role": "system",
                                "content": (
                                    "You are a classifier. Categorize the given query into exactly "
                                    "one of: air, weapon, ground, sensor, comm. Output ONLY that word."
                                ),
                            },
                            {"role": "user", "content": query},
                        ]
                        clf_raw = self._llm.chat(clf_msg).get("content", "").strip().lower()
                        clf_clean = re.sub(r"[^a-z]", "", clf_raw)
                        field = clf_clean if clf_clean in {"air", "weapon", "ground", "sensor", "comm"} else "comm"

                    security_label = (
                        params.get("security_label_filter", ["PUBLIC"])[0]
                        if params.get("security_label_filter")
                        else "PUBLIC"
                    )

                    # BUG-1 fix: use version= (not doc_rev=)
                    # BUG-3 fix: pass source_uri for citation traceability
                    chunks_result = chunk_document(
                        doc_id=doc_id,
                        version="v1",
                        text=text[:10000],
                        security_label=security_label,
                        doc_field=field,
                        source_uri=url,
                        max_tokens=256,
                        overlap=32,
                    )
                    chunks = chunks_result.get("chunks", [])
                    if chunks:
                        # BUG-2 fix: removed c.doc_id reassignment (already set above)
                        self._index.add_chunks(chunks)
                        added_any = True

                        file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
                        try:
                            register_document(
                                self._db_path,
                                {
                                    "doc_id": doc_id,
                                    "doc_rev": "v1",
                                    "title": title[:100] if title else f"WEB_{doc_id}",
                                    "field": field,
                                    "security_label": security_label,
                                    "file_hash": file_hash,
                                },
                            )
                        except Exception as e:
                            print(f"WEB_DOC_DB_REGISTER_ERR: {e}")

                except Exception:
                    pass

            # Persist updated index if a storage path is configured
            if added_any and self._index_path:
                new_version = f"idx-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M')}"
                self._index.save(self._index_path)
                meta_path = os.path.join(self._index_path, "meta.json")
                meta: dict = {}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r") as f:
                            meta = json.load(f)
                    except Exception:
                        pass
                meta["index_version"] = new_version
                with open(meta_path, "w") as f:
                    json.dump(meta, f)
                self._index_version = new_version

            if added_any:
                return self._index.search(
                    query=query,
                    top_k=top_k,
                    field_filter=params.get("field_filter"),
                    security_label_filter=params.get("security_label_filter"),
                )
            return []

        except Exception:
            return []

    def _query_db(self, params: dict) -> List[dict]:
        """Fuzzy keyword search over platforms and weapons tables.

        Matches both raw query and a normalized form (hyphens/spaces stripped,
        uppercased) so "KF-21", "KF21", and "KF 21" all match the same rows.
        """
        from ..knowledge.db_schema import get_connection
        query = params.get("query", "")
        query_lower = query.lower()
        query_norm = _normalize_id(query)

        def _row_matches(row_dict: dict) -> bool:
            for v in row_dict.values():
                if v is None:
                    continue
                sv = str(v)
                if query_lower in sv.lower():
                    return True
                if query_norm and query_norm in _normalize_id(sv):
                    return True
            return False

        conn = get_connection(self._db_path)
        results = []
        try:
            cursor = conn.cursor()
            # Fetch all rows from each table and filter in Python for fuzzy match
            for table in ("platforms", "weapons"):
                try:
                    cursor.execute(f"SELECT * FROM {table}")
                    for row in cursor.fetchall():
                        row_dict = dict(row)
                        if _row_matches(row_dict):
                            results.append(row_dict)
                except Exception:
                    pass
        finally:
            conn.close()
        return results

    def _build_context(self, chunks: List[dict], db_rows: List[dict]) -> str:
        parts = []
        for i, chunk in enumerate(chunks[:5], 1):
            parts.append(f"[문서 {i}] {chunk['text'][:300]}")
        for i, row in enumerate(db_rows[:3], 1):
            parts.append(f"[DB {i}] {json.dumps(row, ensure_ascii=False)}")
        return "\n\n".join(parts)

    def _build_response(
        self,
        request_id: str,
        answer: str,
        citations: List[dict],
        security_label: str,
        error_code: Optional[str] = None,
        tool_call_log: Optional[List[dict]] = None,
    ) -> dict:
        response_body = {
            "request_id": request_id,
            "data": {"answer": answer},
            "citations": citations,
            "security_label": security_label,
            "version": {
                "model": self._model_version,
                "index": self._index_version,
                "db": self._db_schema_version,
            },
        }
        if error_code:
            response_body["error"] = error_code
        if tool_call_log:  # agent mode에서만 포함 — pipeline 응답에는 키 없음
            response_body["tool_call_log"] = tool_call_log

        response_str = json.dumps(response_body, ensure_ascii=False, sort_keys=True)
        response_body["hash"] = hashlib.sha256(response_str.encode()).hexdigest()
        return response_body
