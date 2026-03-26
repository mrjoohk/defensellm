"""Tests for get_tool_definitions_for_llm() in tool_schemas.py."""

import pytest
from defense_llm.agent.tool_schemas import (
    get_tool_definitions_for_llm,
    list_tools,
)


def test_returns_all_tools_by_default():
    defs = get_tool_definitions_for_llm()
    names = {d["function"]["name"] for d in defs}
    for tool in list_tools():
        assert tool in names


def test_openai_format_structure():
    defs = get_tool_definitions_for_llm(["search_docs"])
    assert len(defs) == 1
    d = defs[0]
    assert d["type"] == "function"
    assert "function" in d
    fn = d["function"]
    assert "name" in fn
    assert "description" in fn
    assert "parameters" in fn
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "properties" in params
    assert "required" in params


def test_search_docs_required_fields():
    defs = get_tool_definitions_for_llm(["search_docs"])
    params = defs[0]["function"]["parameters"]
    assert "query" in params["required"]
    assert "query" in params["properties"]
    assert params["properties"]["query"]["type"] == "string"


def test_filtering_by_tool_names():
    defs = get_tool_definitions_for_llm(["search_docs", "security_refusal"])
    names = [d["function"]["name"] for d in defs]
    assert names == ["search_docs", "security_refusal"]


def test_unknown_tool_name_skipped():
    defs = get_tool_definitions_for_llm(["nonexistent_tool"])
    assert defs == []


def test_script_tools_included():
    script_tools = [
        "create_script", "create_batch_script",
        "execute_batch_script", "save_results_csv",
    ]
    defs = get_tool_definitions_for_llm(script_tools)
    names = {d["function"]["name"] for d in defs}
    for t in script_tools:
        assert t in names


def test_create_script_required_fields():
    defs = get_tool_definitions_for_llm(["create_script"])
    params = defs[0]["function"]["parameters"]
    assert "script_path" in params["required"]
    assert "script_content" in params["required"]


def test_array_type_properties_have_items():
    defs = get_tool_definitions_for_llm(["search_docs"])
    props = defs[0]["function"]["parameters"]["properties"]
    assert props["field_filter"]["type"] == "array"
    assert "items" in props["field_filter"]


def test_descriptions_present():
    defs = get_tool_definitions_for_llm(["search_docs"])
    fn = defs[0]["function"]
    assert len(fn["description"]) > 0
    query_prop = fn["parameters"]["properties"]["query"]
    assert "description" in query_prop


def test_search_docs_has_no_online_mode_param():
    """online_mode must NOT appear in search_docs — it is a server-level setting."""
    defs = get_tool_definitions_for_llm(["search_docs"])
    props = defs[0]["function"]["parameters"]["properties"]
    assert "online_mode" not in props, (
        "online_mode must be removed from search_docs tool schema; "
        "use online_mode_enabled on the Executor instead"
    )


def test_web_search_schema_registered():
    defs = get_tool_definitions_for_llm(["web_search"])
    assert len(defs) == 1
    fn = defs[0]["function"]
    assert fn["name"] == "web_search"
    assert "query" in fn["parameters"]["required"]
    assert len(fn["description"]) > 0


def test_web_search_not_in_default_agent_tools():
    """web_search is in the registry but must be explicitly requested.
    The Executor adds it only when online_mode_enabled=True."""
    default_agent_tools = [
        "search_docs", "query_structured_db",
        "generate_answer", "format_response", "security_refusal",
    ]
    defs = get_tool_definitions_for_llm(default_agent_tools)
    names = [d["function"]["name"] for d in defs]
    assert "web_search" not in names


def test_threat_assess_schema_registered():
    """threat_assess는 스키마에 등록되어 있어야 한다."""
    defs = get_tool_definitions_for_llm(["threat_assess"])
    assert len(defs) == 1
    fn = defs[0]["function"]
    assert fn["name"] == "threat_assess"
    assert len(fn["description"]) > 0


def test_threat_assess_required_fields():
    """threat_assess 필수 필드: threat_type, count."""
    defs = get_tool_definitions_for_llm(["threat_assess"])
    params = defs[0]["function"]["parameters"]
    assert "threat_type" in params["required"]
    assert "count" in params["required"]


def test_threat_assess_optional_fields_in_properties():
    """movement, confidence, roe_level, available_fires 등은 optional properties에 있어야 한다."""
    defs = get_tool_definitions_for_llm(["threat_assess"])
    props = defs[0]["function"]["parameters"]["properties"]
    for optional_field in ("movement", "confidence", "roe_level", "available_fires"):
        assert optional_field in props, f"'{optional_field}' missing from threat_assess properties"


def test_threat_assess_not_in_default_agent_tools():
    """threat_assess는 기본 도구 목록에 없음 — battle_context 제공 시에만 활성화."""
    default_agent_tools = [
        "search_docs", "query_structured_db",
        "generate_answer", "format_response", "security_refusal",
    ]
    defs = get_tool_definitions_for_llm(default_agent_tools)
    names = [d["function"]["name"] for d in defs]
    assert "threat_assess" not in names
