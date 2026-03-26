"""
commander_interface.py — Phase 4: Commander's Decision Support Interface

Phase 4 목적: 5개 의사결정 지원 도구를 단일 합성 응답으로 연결하는
             구조적 증명(Structural Proof) 수준의 Commander Interface 구현.

체인 순서:
  threat_assess → ipb_summary → coa_generate → roe_check → fires_plan

설계 원칙:
  - 최소 구현(Structural Proof): 도구 연결 구조와 I/O 계약 검증에 집중.
  - 각 도구는 이전 도구의 출력을 입력으로 활용한다 (데이터 의존성 체인).
  - fires_plan은 available_fires가 있을 때만 실행한다.
  - 함수는 llm_adapter 및 threat_assess_fn을 매개변수로 받아 독립 테스트 가능.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .decision_support import (
    coa_generate,
    ipb_summary,
    roe_check,
    fires_plan,
)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def compose_decision_support_response(
    arguments: dict,
    llm_adapter: Any,
    threat_assess_fn: Callable[[dict], dict],
) -> dict:
    """Phase 4 Commander Interface: 5개 도구를 순차적으로 실행하여
    단일 의사결정 지원 패키지(Decision Support Package)를 반환한다.

    체인 데이터 흐름:
        threat_assess → ipb_summary → coa_generate → roe_check → fires_plan

    Args:
        arguments: 합성 도구 입력 딕셔너리 (스키마: decision_support_composite).
        llm_adapter: LLM 어댑터 (AbstractLLMAdapter 호환).
        threat_assess_fn: Executor._threat_assess 등 threat_assess 핸들러.

    Returns:
        DecisionSupportPackage 딕셔너리.
        키: package_type, execution_chain, threat_assessment,
            ipb_summary, coa_recommendation, roe_validation, fires_plan.
    """
    execution_chain: List[str] = []
    errors: List[str] = []

    # ── Step 1: threat_assess ───────────────────────────────────────────────
    ta_args = {
        "threat_type":      arguments.get("threat_type", "MIXED"),
        "count":            arguments.get("threat_count", 1),
        "movement":         arguments.get("movement", "UNKNOWN"),
        "confidence":       arguments.get("confidence", 0.7),
        "roe_level":        arguments.get("roe_level", "RETURN_FIRE"),
        "available_fires":  arguments.get("available_fires", []),
        "friendly_unit_type": arguments.get("friendly_unit_type", ""),
    }
    ta_result = _safe_call(
        "threat_assess", threat_assess_fn, ta_args,
        execution_chain, errors,
    )

    threat_level = ta_result.get("threat_level", "MEDIUM") if ta_result else "MEDIUM"

    # ── Step 2: ipb_summary ─────────────────────────────────────────────────
    ipb_args = {
        "threat_type":               arguments.get("threat_type", "MIXED"),
        "terrain_type":              arguments.get("terrain_type", "MIXED"),
        "weather":                   arguments.get("weather", "CLEAR"),
        "time_of_day":               arguments.get("time_of_day", "DAY"),
        "intel_source_reliability":  arguments.get("intel_source_reliability", "C"),
        "intel_credibility":         arguments.get("intel_credibility", "3"),
        "known_gaps":                arguments.get("known_gaps", []),
        "visibility_km":             arguments.get("visibility_km", 10.0),
    }
    ipb_result = _safe_call(
        "ipb_summary", lambda a: ipb_summary(a, llm_adapter), ipb_args,
        execution_chain, errors,
    )

    # ── Step 3: coa_generate — threat_level은 threat_assess 결과 사용 ────────
    coa_args = {
        "threat_type":      arguments.get("threat_type", "MIXED"),
        "threat_level":     threat_level,             # ← Step 1 출력 활용
        "friendly_strength": arguments.get("friendly_strength", "미상"),
        "terrain":          arguments.get("terrain_type", "MIXED"),
        "roe_level":        arguments.get("roe_level", "RETURN_FIRE"),
        "ttl_minutes":      arguments.get("ttl_minutes", 30),
        "priority_factors": arguments.get("priority_factors", []),
        "num_coas":         3,
    }
    coa_result = _safe_call(
        "coa_generate", lambda a: coa_generate(a, llm_adapter), coa_args,
        execution_chain, errors,
    )

    # ── Step 4: roe_check — 권고 COA에 대한 ROE 검증 ───────────────────────
    recommended_action = _extract_recommended_action(coa_result)
    roe_args = {
        "proposed_action":       recommended_action,
        "roe_level":             arguments.get("roe_level", "RETURN_FIRE"),
        "target_type":           arguments.get("target_type", "MILITARY"),
        "collateral_risk":       arguments.get("collateral_risk", "LOW"),
        "hostile_act_confirmed": threat_level in ("HIGH", "CRITICAL"),  # ← Step 1 활용
    }
    roe_result = _safe_call(
        "roe_check", roe_check, roe_args,
        execution_chain, errors,
    )

    # ── Step 5: fires_plan — available_fires가 있을 때만 실행 ────────────────
    fires_result: Optional[dict] = None
    available_fires = arguments.get("available_fires", [])
    if available_fires:
        fires_args = {
            "threat_type":     arguments.get("threat_type", "MIXED"),
            "threat_location": arguments.get("threat_location", "미상"),
            "threat_count":    arguments.get("threat_count", 1),
            "available_fires": available_fires,
            "roe_level":       arguments.get("roe_level", "RETURN_FIRE"),
            "no_fire_areas":   arguments.get("no_fire_areas", []),
            "priority":        arguments.get("priority", "SUPPRESSION"),
        }
        fires_result = _safe_call(
            "fires_plan", fires_plan, fires_args,
            execution_chain, errors,
        )

    return {
        "package_type":       "DECISION_SUPPORT_COMPOSITE",
        "execution_chain":    execution_chain,
        "errors":             errors,
        # ── Individual tool outputs ─────────────────────────────────────────
        "threat_assessment":  ta_result,
        "ipb_summary":        ipb_result,
        "coa_recommendation": coa_result,
        "roe_validation":     roe_result,
        "fires_plan":         fires_result,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _safe_call(
    tool_name: str,
    fn: Callable,
    args: dict,
    execution_chain: List[str],
    errors: List[str],
) -> Optional[dict]:
    """Call *fn(args)* and log the result.

    Appends *tool_name* to *execution_chain* on success.
    Appends an error string to *errors* on exception.
    Returns None on exception so the chain can continue.
    """
    try:
        result = fn(args)
        execution_chain.append(tool_name)
        return result
    except Exception as exc:
        errors.append(f"{tool_name}: {exc}")
        execution_chain.append(f"{tool_name}[ERROR]")
        return None


def _extract_recommended_action(coa_result: Optional[dict]) -> str:
    """Extract the recommended COA name from a coa_generate result.

    Used as the proposed_action input to roe_check.
    Falls back to "방어 행동" if coa_result is None or malformed.
    """
    if not coa_result:
        return "방어 행동"

    recommended_id = coa_result.get("recommended_coa")
    coas = coa_result.get("coas", [])

    if recommended_id and coas:
        for coa in coas:
            if coa.get("coa_id") == recommended_id:
                return coa.get("name", "방어 행동")

    # 첫 번째 COA 이름으로 폴백
    if coas:
        return coas[0].get("name", "방어 행동")

    return "방어 행동"
