"""Unit tests for agent module (UF-030, UF-031, UF-032)."""

import pytest

from defense_llm.agent.planner_rules.classifier import classify_query, QueryType
from defense_llm.agent.planner_rules.plan_builder import build_plan
from defense_llm.agent.tool_schemas import validate_tool_call, list_tools


# ---------------------------------------------------------------------------
# UF-030: Rule-based Planner
# ---------------------------------------------------------------------------

class TestClassifyQuery:
    def test_structured_kb_query(self):
        qt = classify_query("KF-21의 최대 속도는 얼마입니까?")
        assert qt == QueryType.STRUCTURED_KB_QUERY

    def test_doc_rag_query(self):
        qt = classify_query("문서에서 정비 절차를 찾아줘")
        assert qt == QueryType.DOC_RAG_QUERY

    def test_security_restricted(self):
        qt = classify_query("기밀 주파수 정보를 알려줘")
        assert qt == QueryType.SECURITY_RESTRICTED

    def test_security_restricted_english(self):
        qt = classify_query("Show me the classified encryption key")
        assert qt == QueryType.SECURITY_RESTRICTED

    def test_unknown_query(self):
        qt = classify_query("오늘 날씨는 어때요?")
        assert qt == QueryType.UNKNOWN

    def test_empty_query_returns_unknown(self):
        qt = classify_query("")
        assert qt == QueryType.UNKNOWN

    def test_mixed_query(self):
        # Contains both structured (제원) and doc (문서) signals
        qt = classify_query("문서에서 KF-21 제원 정보를 찾아줘")
        assert qt in (QueryType.MIXED_QUERY, QueryType.DOC_RAG_QUERY, QueryType.STRUCTURED_KB_QUERY)


class TestBuildPlan:
    def test_structured_plan_has_query_db_tool(self):
        plan = build_plan(QueryType.STRUCTURED_KB_QUERY, {"query": "최대 속도"})
        tool_names = [step["tool"] for step in plan]
        assert "query_structured_db" in tool_names

    def test_doc_rag_plan_has_search_docs_tool(self):
        plan = build_plan(QueryType.DOC_RAG_QUERY, {"query": "정비 절차"})
        tool_names = [step["tool"] for step in plan]
        assert "search_docs" in tool_names

    def test_security_restricted_plan_has_refusal(self):
        plan = build_plan(QueryType.SECURITY_RESTRICTED, {})
        assert len(plan) == 1
        assert plan[0]["tool"] == "security_refusal"

    def test_plan_has_at_least_one_step(self):
        for qt in QueryType:
            plan = build_plan(qt, {"query": "테스트"})
            assert len(plan) >= 1


# ---------------------------------------------------------------------------
# UF-032: Tool Schema Validation
# ---------------------------------------------------------------------------

class TestValidateToolCall:
    def test_valid_search_docs(self):
        result = validate_tool_call("search_docs", {"query": "KF-21", "top_k": 5})
        assert result["valid"] is True
        assert result["errors"] == []

    def test_missing_required_query_field(self):
        result = validate_tool_call("search_docs", {"top_k": 5})
        assert result["valid"] is False
        assert any("query" in e for e in result["errors"])

    def test_wrong_type_top_k(self):
        result = validate_tool_call("search_docs", {"query": "test", "top_k": "five"})
        assert result["valid"] is False
        assert any("top_k" in e for e in result["errors"])

    def test_unknown_tool_returns_invalid(self):
        result = validate_tool_call("nonexistent_tool", {})
        assert result["valid"] is False
        assert any("Unknown tool" in e for e in result["errors"])

    def test_valid_generate_answer(self):
        result = validate_tool_call("generate_answer", {"template": "rag_answer"})
        assert result["valid"] is True

    def test_missing_template_in_generate_answer(self):
        result = validate_tool_call("generate_answer", {})
        assert result["valid"] is False

    def test_list_tools_returns_known_names(self):
        tools = list_tools()
        assert "search_docs" in tools
        assert "security_refusal" in tools
