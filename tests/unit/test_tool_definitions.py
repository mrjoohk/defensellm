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
