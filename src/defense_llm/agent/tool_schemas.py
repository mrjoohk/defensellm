"""JSON Schema definitions and validation for all tools (UF-032)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

E_VALIDATION = "E_VALIDATION"

# ---------------------------------------------------------------------------
# Tool schemas — each schema maps to the "params" dict of a tool call
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: Dict[str, dict] = {
    "search_docs": {
        "required": ["query"],
        "properties": {
            "query": {"type": str},
            "top_k": {"type": int},
            "field_filter": {"type": list},
            "security_label_filter": {"type": list},
        },
    },
    "web_search": {
        "required": ["query"],
        "properties": {
            "query": {"type": str},
            "top_k": {"type": int},
        },
    },
    "query_structured_db": {
        "required": ["query"],
        "properties": {
            "query": {"type": str},
            "field_filter": {"type": list},
            "security_label_filter": {"type": list},
        },
    },
    "generate_answer": {
        "required": ["template"],
        "properties": {
            "template": {"type": str},
        },
    },
    "format_response": {
        "required": ["template"],
        "properties": {
            "template": {"type": str},
        },
    },
    "security_refusal": {
        "required": ["reason"],
        "properties": {
            "reason": {"type": str},
        },
    },
    # -----------------------------------------------------------------------
    # Battle situation tools
    # -----------------------------------------------------------------------
    "threat_assess": {
        "required": ["threat_type", "count"],
        "properties": {
            "threat_type": {"type": str},
            "count": {"type": int},
            "movement": {"type": str},
            "confidence": {"type": float},
            "roe_level": {"type": str},
            "available_fires": {"type": list},
            "friendly_unit_type": {"type": str},
        },
    },
    # -----------------------------------------------------------------------
    # Phase 3 decision support tools
    # -----------------------------------------------------------------------
    "coa_generate": {
        "required": ["threat_type", "threat_level"],
        "properties": {
            "threat_type":        {"type": str},
            "threat_level":       {"type": str},
            "friendly_strength":  {"type": str},
            "terrain":            {"type": str},
            "roe_level":          {"type": str},
            "ttl_minutes":        {"type": int},
            "priority_factors":   {"type": list},
            "num_coas":           {"type": int},
        },
    },
    "ipb_summary": {
        "required": ["threat_type"],
        "properties": {
            "threat_type":               {"type": str},
            "terrain_type":              {"type": str},
            "weather":                   {"type": str},
            "time_of_day":               {"type": str},
            "intel_source_reliability":  {"type": str},
            "intel_credibility":         {"type": str},
            "known_gaps":                {"type": list},
            "visibility_km":             {"type": float},
        },
    },
    "roe_check": {
        "required": ["proposed_action", "roe_level"],
        "properties": {
            "proposed_action":        {"type": str},
            "roe_level":              {"type": str},
            "target_type":            {"type": str},
            "collateral_risk":        {"type": str},
            "hostile_act_confirmed":  {"type": bool},
        },
    },
    "fires_plan": {
        "required": ["threat_type", "available_fires"],
        "properties": {
            "threat_type":      {"type": str},
            "threat_location":  {"type": str},
            "threat_count":     {"type": int},
            "available_fires":  {"type": list},
            "roe_level":        {"type": str},
            "no_fire_areas":    {"type": list},
            "priority":         {"type": str},
        },
    },
    # -----------------------------------------------------------------------
    # Phase 4: Commander Interface — composite decision support tool
    # -----------------------------------------------------------------------
    "decision_support_composite": {
        "required": ["threat_type"],
        "properties": {
            "threat_type":               {"type": str},
            "threat_count":              {"type": int},
            "movement":                  {"type": str},
            "confidence":                {"type": float},
            "roe_level":                 {"type": str},
            "available_fires":           {"type": list},
            "friendly_unit_type":        {"type": str},
            "friendly_strength":         {"type": str},
            "terrain_type":              {"type": str},
            "weather":                   {"type": str},
            "time_of_day":               {"type": str},
            "intel_source_reliability":  {"type": str},
            "intel_credibility":         {"type": str},
            "known_gaps":                {"type": list},
            "visibility_km":             {"type": float},
            "ttl_minutes":               {"type": int},
            "priority_factors":          {"type": list},
            "threat_location":           {"type": str},
            "no_fire_areas":             {"type": list},
            "priority":                  {"type": str},
            "target_type":               {"type": str},
            "collateral_risk":           {"type": str},
        },
    },
    # -----------------------------------------------------------------------
    # Agentic execution tools (script pipeline)
    # -----------------------------------------------------------------------
    "create_script": {
        "required": ["script_path", "script_content"],
        "properties": {
            "script_path": {"type": str},
            "script_content": {"type": str},
            "overwrite": {"type": bool},
        },
    },
    "create_batch_script": {
        "required": ["batch_path", "script_path"],
        "properties": {
            "batch_path": {"type": str},
            "script_path": {"type": str},
            "python_exe": {"type": str},
            "extra_args": {"type": list},
        },
    },
    "execute_batch_script": {
        "required": ["batch_path"],
        "properties": {
            "batch_path": {"type": str},
            "timeout_seconds": {"type": int},
            "capture_output": {"type": bool},
        },
    },
    "save_results_csv": {
        "required": ["data", "csv_path"],
        "properties": {
            "data": {"type": list},
            "csv_path": {"type": str},
            "encoding": {"type": str},
        },
    },
}

# ---------------------------------------------------------------------------
# Human-readable descriptions for LLM tool definitions (Korean/English)
# ---------------------------------------------------------------------------

_TOOL_DESCRIPTIONS: Dict[str, Dict[str, Any]] = {
    "search_docs": {
        "tool": "방산 문서 인덱스에서 관련 청크를 하이브리드(BM25+Dense) 방식으로 검색합니다. 내부 지식 베이스(오프라인) 전용입니다.",
        "params": {
            "query": "검색할 자연어 질의",
            "top_k": "반환할 최대 결과 수 (기본값: 5)",
            "field_filter": "도메인 필드 필터 (air/weapon/ground/sensor/comm)",
            "security_label_filter": "보안 등급 필터 (PUBLIC/INTERNAL/RESTRICTED/SECRET)",
        },
    },
    "web_search": {
        "tool": (
            "인터넷 웹 검색으로 내부 문서에 없는 최신 공개 정보를 조회합니다. "
            "search_docs로 관련 문서를 찾지 못한 경우에만 호출하십시오. "
            "보안 정책에 따라 비활성화될 수 있습니다."
        ),
        "params": {
            "query": "검색할 자연어 질의",
            "top_k": "반환할 최대 결과 수 (기본값: 3)",
        },
    },
    "query_structured_db": {
        "tool": "플랫폼/무장/제약 정형 데이터베이스에서 관련 레코드를 검색합니다.",
        "params": {
            "query": "검색할 플랫폼명, 무장명, 또는 키워드",
            "field_filter": "도메인 필드 필터",
            "security_label_filter": "보안 등급 필터",
        },
    },
    "generate_answer": {
        "tool": "수집된 컨텍스트를 기반으로 최종 답변을 생성합니다.",
        "params": {"template": "답변 생성에 사용할 프롬프트 템플릿"},
    },
    "format_response": {
        "tool": "응답을 최종 포맷으로 정리합니다.",
        "params": {"template": "포맷 템플릿"},
    },
    "security_refusal": {
        "tool": "보안 정책에 따라 요청을 거부합니다.",
        "params": {"reason": "거부 사유"},
    },
    "threat_assess": {
        "tool": (
            "전투 상황 컨텍스트의 위협 정보를 분석하여 위협 수준, 위협 점수, "
            "권고 행동 방책을 규칙 기반으로 평가합니다. "
            "battle_context에 threat 정보가 있을 때 THREAT_ASSESS intent 처리에 우선 호출하십시오."
        ),
        "params": {
            "threat_type": "위협 유형 (ARMOR/INFANTRY/AIR/NAVAL/MISSILE/DRONE/CYBER/MIXED)",
            "count": "위협 수량",
            "movement": "이동 상태 (ADVANCING/RETREATING/FLANKING/STATIONARY/UNKNOWN)",
            "confidence": "위협 정보 신뢰도 (0.0~1.0)",
            "roe_level": "현행 교전규칙 (HOLD/RETURN_FIRE/FIRE_AT_WILL/WEAPONS_FREE)",
            "available_fires": "가용 화력 자산 목록",
            "friendly_unit_type": "아군 부대 유형 (COA 맥락화용)",
        },
    },
    "coa_generate": {
        "tool": (
            "위협 수준과 아군 전력을 기반으로 3개의 행동 방책(COA)을 생성합니다. "
            "각 COA는 성공 확률, 장단점, ROE 준수 여부를 포함합니다. "
            "threat_assess 결과를 입력으로 활용하십시오."
        ),
        "params": {
            "threat_type":       "위협 유형 (ARMOR/INFANTRY/AIR/NAVAL/MISSILE/DRONE/CYBER/MIXED)",
            "threat_level":      "threat_assess가 반환한 위협 수준 (CRITICAL/HIGH/MEDIUM/LOW/MINIMAL)",
            "friendly_strength": "아군 전력 요약 (선택)",
            "terrain":           "지형 유형 또는 설명 (선택)",
            "roe_level":         "현행 교전규칙 (선택)",
            "ttl_minutes":       "결심 가능 시간 제한 분 (선택)",
            "priority_factors":  "사령관 우선 고려 요소 목록 (선택)",
            "num_coas":          "생성할 방책 수 (기본값: 3)",
        },
    },
    "ipb_summary": {
        "tool": (
            "전장 정보 준비(IPB)를 수행합니다. OCOKA 분석(관측·엄폐·장애물·핵심지형·접근로), "
            "위협 능력·취약점·의도, 가장 가능한/위험한 적 행동방침을 도출합니다."
        ),
        "params": {
            "threat_type":              "위협 유형",
            "terrain_type":             "지형 유형 (URBAN/FOREST/OPEN/MOUNTAIN/COASTAL/DESERT/MIXED)",
            "weather":                  "기상 (CLEAR/CLOUDY/RAIN/FOG/SNOW/STORM)",
            "time_of_day":              "주야 구분 (DAWN/DAY/DUSK/NIGHT)",
            "intel_source_reliability": "출처 신뢰도 (NATO A~F)",
            "intel_credibility":        "내용 신빙성 (NATO 1~6)",
            "known_gaps":               "알려진 정보 공백 목록",
            "visibility_km":            "현재 관측 가능 거리 km",
        },
    },
    "roe_check": {
        "tool": (
            "제안된 행동이 현행 ROE를 준수하는지 규칙 기반으로 검증합니다. "
            "FULLY / CONDITIONALLY / NON_COMPLIANT 판정과 위반 사항 및 조건을 반환합니다. "
            "LLM 판단 없이 순수 규칙 테이블로 실행됩니다."
        ),
        "params": {
            "proposed_action":       "검증할 행동 설명 (예: '155mm 포대로 적 전차 종대 사격')",
            "roe_level":             "현행 교전규칙 (HOLD/RETURN_FIRE/FIRE_AT_WILL/WEAPONS_FREE)",
            "target_type":           "표적 유형 (MILITARY/DUAL_USE/CIVILIAN, 기본값: MILITARY)",
            "collateral_risk":       "민간 피해 위험 (LOW/MEDIUM/HIGH, 기본값: LOW)",
            "hostile_act_confirmed": "적 선제 행위 확인 여부 (bool, 기본값: false)",
        },
    },
    "fires_plan": {
        "tool": (
            "위협 특성에 최적화된 화력 지원 계획을 수립합니다. "
            "가용 화력 자산을 위협 유형별 효과도로 순위화하고 순차 사격 임무를 배분합니다. "
            "사격 금지 구역(NFA) 준수 여부를 포함합니다."
        ),
        "params": {
            "threat_type":     "위협 유형",
            "threat_location": "위협 위치 (MGRS 또는 설명)",
            "threat_count":    "위협 수량",
            "available_fires": "가용 화력 자산 목록 (필수, 예: ['155mm SPH Battery', 'AT Missiles'])",
            "roe_level":       "현행 교전규칙",
            "no_fire_areas":   "사격 금지 구역 식별자 목록",
            "priority":        "사격 우선 목적 (DESTRUCTION/SUPPRESSION/NEUTRALIZATION/DELAY)",
        },
    },
    # -----------------------------------------------------------------------
    # Phase 4: Commander Interface composite tool description
    # -----------------------------------------------------------------------
    "decision_support_composite": {
        "tool": (
            "Phase 4 Commander Interface: 단일 호출로 위협 평가(threat_assess) → "
            "전장 정보 준비(ipb_summary) → 행동 방책 생성(coa_generate) → "
            "ROE 검증(roe_check) → 화력 계획(fires_plan) 체인을 실행합니다. "
            "전투 상황 컨텍스트가 있을 때 사령관 결심 지원 패키지 전체를 한 번에 요청하십시오."
        ),
        "params": {
            "threat_type":              "위협 유형 (ARMOR/INFANTRY/AIR/NAVAL/MISSILE/DRONE/CYBER/MIXED, 필수)",
            "threat_count":             "위협 수량 (기본값: 1)",
            "movement":                 "이동 상태 (ADVANCING/RETREATING/FLANKING/STATIONARY/UNKNOWN)",
            "confidence":               "위협 신뢰도 (0.0~1.0, 기본값: 0.7)",
            "roe_level":                "교전규칙 (HOLD/RETURN_FIRE/FIRE_AT_WILL/WEAPONS_FREE)",
            "available_fires":          "가용 화력 자산 목록 (없으면 fires_plan 단계 생략)",
            "friendly_unit_type":       "아군 부대 유형",
            "friendly_strength":        "아군 전력 요약",
            "terrain_type":             "지형 유형",
            "weather":                  "기상",
            "time_of_day":              "주야 구분",
            "intel_source_reliability": "출처 신뢰도 (NATO A~F)",
            "intel_credibility":        "내용 신빙성 (NATO 1~6)",
            "known_gaps":               "알려진 정보 공백 목록",
            "visibility_km":            "관측 가능 거리 km",
            "ttl_minutes":              "결심 가능 시간 분",
            "priority_factors":         "사령관 우선 고려 요소 목록",
            "threat_location":          "위협 위치 (MGRS 또는 설명)",
            "no_fire_areas":            "사격 금지 구역 목록",
            "priority":                 "화력 우선 목적 (DESTRUCTION/SUPPRESSION/NEUTRALIZATION/DELAY)",
            "target_type":              "표적 유형 (MILITARY/DUAL_USE/CIVILIAN)",
            "collateral_risk":          "민간 피해 위험 (LOW/MEDIUM/HIGH)",
        },
    },
    "create_script": {
        "tool": "Python 스크립트를 허용된 경로에 파일로 생성합니다.",
        "params": {
            "script_path": "스크립트를 저장할 절대 경로",
            "script_content": "Python 소스 코드 문자열",
            "overwrite": "기존 파일 덮어쓰기 여부 (기본값: false)",
        },
    },
    "create_batch_script": {
        "tool": "Python 스크립트를 실행하는 배치(.bat/.sh) 파일을 생성합니다.",
        "params": {
            "batch_path": "배치 파일을 저장할 절대 경로",
            "script_path": "실행할 Python 스크립트의 절대 경로",
            "python_exe": "Python 실행 파일 경로 (기본값: python)",
            "extra_args": "스크립트에 전달할 추가 인수 목록",
        },
    },
    "execute_batch_script": {
        "tool": "배치 스크립트를 서브프로세스로 실행하고 결과를 반환합니다.",
        "params": {
            "batch_path": "실행할 배치 파일의 절대 경로",
            "timeout_seconds": "최대 실행 대기 시간(초) (기본값: 300)",
            "capture_output": "stdout/stderr 캡처 여부 (기본값: true)",
        },
    },
    "save_results_csv": {
        "tool": "딕셔너리 리스트를 CSV 파일로 저장합니다.",
        "params": {
            "data": "저장할 딕셔너리 리스트 (각 딕셔너리가 한 행)",
            "csv_path": "CSV 파일을 저장할 절대 경로",
            "encoding": "파일 인코딩 (기본값: utf-8-sig, Excel 호환)",
        },
    },
}


def _python_type_to_json_type(py_type: type) -> str:
    """Convert a Python type to its JSON Schema type string."""
    return {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }.get(py_type, "string")


def get_tool_definitions_for_llm(
    tool_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return OpenAI-format tool definitions for injection into LLM context.

    Args:
        tool_names: Optional whitelist of tool names to include.
                    If None, all registered tools are returned.

    Returns:
        List of OpenAI-format tool definition dicts:
        [{"type": "function", "function": {"name": ..., "description": ...,
                                           "parameters": {...}}}]
    """
    names = tool_names if tool_names is not None else list(_TOOL_SCHEMAS.keys())
    definitions: List[Dict[str, Any]] = []

    for name in names:
        schema = _TOOL_SCHEMAS.get(name)
        if schema is None:
            continue
        desc_info = _TOOL_DESCRIPTIONS.get(name, {})
        tool_desc = desc_info.get("tool", name)
        param_descs = desc_info.get("params", {})

        properties: Dict[str, Any] = {}
        for prop_name, constraints in schema.get("properties", {}).items():
            py_type = constraints.get("type", str)
            prop_def: Dict[str, Any] = {
                "type": _python_type_to_json_type(py_type),
            }
            if prop_name in param_descs:
                prop_def["description"] = param_descs[prop_name]
            if py_type is list:
                prop_def["items"] = {"type": "string"}
            definitions_entry_props = prop_def
            properties[prop_name] = definitions_entry_props

        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool_desc,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": schema.get("required", []),
                    },
                },
            }
        )

    return definitions


def validate_tool_call(tool_name: str, params: dict) -> dict:
    """Validate tool call parameters against the registered JSON schema (UF-032).

    Args:
        tool_name: Name of the tool being called.
        params: Parameters dict to validate.

    Returns:
        dict with keys: valid (bool), errors (list of str).
    """
    schema = _TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return {
            "valid": False,
            "errors": [f"Unknown tool: '{tool_name}'"],
        }

    errors: List[str] = []

    # Check required fields
    for req in schema.get("required", []):
        if req not in params or params[req] is None:
            errors.append(f"Missing required field: '{req}'")

    # Check type constraints for present fields
    for field, constraints in schema.get("properties", {}).items():
        if field in params and params[field] is not None:
            expected_type = constraints.get("type")
            if expected_type and not isinstance(params[field], expected_type):
                errors.append(
                    f"Field '{field}' expected type {expected_type.__name__}, "
                    f"got {type(params[field]).__name__}"
                )

    return {"valid": len(errors) == 0, "errors": errors}


def list_tools() -> List[str]:
    """Return list of registered tool names."""
    return list(_TOOL_SCHEMAS.keys())
