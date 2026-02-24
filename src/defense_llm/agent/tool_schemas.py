"""JSON Schema definitions and validation for all tools (UF-032)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

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
}


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
