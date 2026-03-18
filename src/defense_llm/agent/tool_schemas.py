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
            "online_mode": {"type": bool},
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
        "tool": "방산 문서 인덱스에서 관련 청크를 하이브리드(BM25+Dense) 방식으로 검색합니다.",
        "params": {
            "query": "검색할 자연어 질의",
            "top_k": "반환할 최대 결과 수 (기본값: 5)",
            "field_filter": "도메인 필드 필터 (air/weapon/ground/sensor/comm)",
            "security_label_filter": "보안 등급 필터 (PUBLIC/INTERNAL/RESTRICTED/SECRET)",
            "online_mode": "온라인 웹 검색 폴백 활성화 여부",
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
