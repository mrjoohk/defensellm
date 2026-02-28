"""LLM-driven Executor: tool dispatch + schema validation + response template (UF-031)."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional

from ..security.rbac import check_access
from ..rag.citation import package_citations
from ..audit.logger import AuditLogger
from .tool_schemas import validate_tool_call

E_AUTH = "E_AUTH"
E_VALIDATION = "E_VALIDATION"
E_INTERNAL = "E_INTERNAL"

_CLEARANCE_ORDER = ["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"]


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
    ) -> None:
        self._llm = llm_adapter
        self._index = index
        self._db_path = db_path
        self._audit = audit_logger
        self._model_version = model_version
        self._index_version = index_version
        self._db_schema_version = db_schema_version
        self._index_path = index_path

    def execute(
        self,
        tool_plan: List[dict],
        user_context: dict,
        request_id: Optional[str] = None,
    ) -> dict:
        """Execute a tool plan and return a standard response (UF-031).

        Args:
            tool_plan: List of { tool: str, params: dict } dicts.
            user_context: { role: str, clearance: str }.
            request_id: Optional pre-assigned request UUID.

        Returns:
            Standard response schema dict.
        """
        request_id = request_id or str(uuid.uuid4())
        error_code: Optional[str] = None
        citations: List[dict] = []
        answer_text = ""

        try:
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
        )

        self._audit.write(
            request_id=request_id,
            user_id=user_context.get("user_id", "unknown"),
            query=str(tool_plan),
            model_version=self._model_version,
            index_version=self._index_version,
            citations=citations,
            response_hash=response["hash"],
            error_code=error_code,
        )

        return response

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
                # Access check before search
                access = check_access(
                    user=user_context,
                    resource_security_labels=params.get("security_label_filter", ["PUBLIC"]),
                )
                if not access["allowed"]:
                    raise PermissionError(f"{E_AUTH}: {access['reason']}")

                query = params["query"]
                
                results = self._index.search(
                    query=query,
                    top_k=params.get("top_k", 5),
                    field_filter=params.get("field_filter"),
                    security_label_filter=params.get("security_label_filter"),
                )
                
                # UF-022: Dynamic Web Search Fallback
                if params.get("online_mode"):
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
            sys_msg = (
                "당신은 방산 도메인 지식 보조 AI입니다. "
                "제공된 근거 자료에 질문에 대한 명확한 답이 없다면, "
                "반드시 '관련 문서를 찾을 수 없습니다.'라고만 답변하고 추가적인 내용을 덧붙이지 마십시오. "
                "답변이 가능하다면 검색된 문서 내용만을 바탕으로 답변해야 하며, "
                "한국어로 출력하고 답변에 사용된 출처 표기는 생략하십시오."
            )
            messages = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"질문: {query_text}\n\n근거 자료:\n{context_text}"},
            ]
            llm_resp = self._llm.chat(messages)
            answer = llm_resp.get("content", "").strip()

            # Prevent showing citations if the system fails to find relevant information
            if "관련 문서를 찾을 수 없습니다" in answer or "문서를 찾을 수 없" in answer:
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
        """UF-022: Dynamic Web Search Fallback."""
        import requests
        from bs4 import BeautifulSoup
        from duckduckgo_search import DDGS
        from ..rag.chunker import chunk_document
        import json
        import os
        import datetime

        query = params.get("query", "")
        if not query:
            return []

        try:
            ddgs = DDGS()
            search_results = list(ddgs.text(query, max_results=2))

            added_any = False
            for i, result in enumerate(search_results):
                url = result.get("href")
                title = result.get("title", "")
                bodyText = result.get("body", "")
                if not url or not bodyText:
                    continue
                try:
                    text = f"{title}\n\n{bodyText}"
                    
                    doc_id = f"WEB-{abs(hash(url)) % 100000}"
                    
                    ff = params.get("field_filter")
                    if not ff:
                        clf_msg = [
                            {"role": "system", "content": "You are a classifier. Categorize the given query into exactly one of: air, weapon, ground, sensor, comm. Output ONLY the single word representing the category."},
                            {"role": "user", "content": query}
                        ]
                        clf_resp = self._llm.chat(clf_msg).get("content", "").strip().lower()
                        import re
                        clf_resp = re.sub(r'[^a-z]', '', clf_resp)

                        if clf_resp in {"air", "weapon", "ground", "sensor", "comm"}:
                            field = clf_resp
                        else:
                            field = "comm"
                    else:
                        field = ff[0]
                        
                    security_label = params.get("security_label_filter", ["PUBLIC"])[0] if params.get("security_label_filter") else "PUBLIC"

                    chunks_result = chunk_document(
                        doc_id=doc_id,
                        doc_rev="v1",
                        text=text[:10000],  # Limit text length to avoid memory blowup
                        security_label=security_label,
                        doc_field=field,
                        max_tokens=256,
                        overlap=32,
                    )
                    chunks = chunks_result.get("chunks", [])
                    if chunks:
                        for c in chunks:
                            c.doc_id = doc_id  # ensure ID aligns
                            
                        self._index.add_chunks(chunks)
                        added_any = True

                        from ..knowledge.document_meta import register_document
                        import hashlib
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
                                }
                            )
                        except Exception as e:
                            print(f"WEB_DOC_DB_REGISTER_ERR: {e}")

                except Exception:
                    pass

            if added_any and self._index_path:
                new_version = f"idx-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M')}"
                self._index.save(self._index_path)
                meta_path = os.path.join(self._index_path, "meta.json")
                meta = {}
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
                    top_k=params.get("top_k", 5),
                    field_filter=params.get("field_filter"),
                    security_label_filter=params.get("security_label_filter"),
                )
            return []

        except Exception:
            return []

    def _query_db(self, params: dict) -> List[dict]:
        """Simple keyword search over platforms/weapons tables."""
        from ..knowledge.db_schema import get_connection
        query = params.get("query", "")
        conn = get_connection(self._db_path)
        results = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM platforms WHERE name LIKE ? OR platform_id LIKE ?",
                (f"%{query}%", f"%{query}%"),
            )
            for row in cursor.fetchall():
                results.append(dict(row))
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

        response_str = json.dumps(response_body, ensure_ascii=False, sort_keys=True)
        response_body["hash"] = hashlib.sha256(response_str.encode()).hexdigest()
        return response_body
