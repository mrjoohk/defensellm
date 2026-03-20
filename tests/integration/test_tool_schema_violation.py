"""Integration tests: IF-005 — Tool schema violation → safe response."""

import uuid

import pytest

from defense_llm.agent.executor import Executor


class TestToolSchemaViolationIF005:
    """IF-005: 툴 호출 스키마 위반 → Executor 실패 처리 → 안전 응답"""

    def test_schema_violation_returns_e_validation(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-005-01: Schema violation returns E_VALIDATION."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        # search_docs with missing 'query' field (required)
        plan = [{"tool": "search_docs", "params": {"top_k": 5}}]
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "schema-test"}
        response = executor.execute(plan, user)

        assert response.get("error") == "E_VALIDATION"

    def test_schema_violation_produces_empty_citations(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-005-02: No partial results leaked on schema violation."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        plan = [{"tool": "search_docs", "params": {"top_k": "not-an-int"}}]
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "schema-test"}
        response = executor.execute(plan, user)

        assert response["citations"] == []

    def test_system_continues_after_violation(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-005-03: System handles subsequent valid requests after schema violation."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        # First: violating request
        bad_plan = [{"tool": "search_docs", "params": {}}]
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "cont-test"}
        response1 = executor.execute(bad_plan, user)
        assert response1.get("error") == "E_VALIDATION"

        # Second: valid request
        good_plan = [{"tool": "search_docs", "params": {"query": "항공 정비", "security_label_filter": ["PUBLIC", "INTERNAL"]}}]
        response2 = executor.execute(good_plan, user)
        assert "error" not in response2 or response2.get("error") != "E_VALIDATION"
        assert "data" in response2

    def test_audit_log_records_schema_violation(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-005-04: Audit log records schema violation."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        request_id = str(uuid.uuid4())
        plan = [{"tool": "search_docs", "params": {}}]  # missing required query
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "audit-schema-test"}
        executor.execute(plan, user, request_id=request_id)

        record = audit_logger.fetch_by_request_id(request_id)
        assert record is not None
        assert record["error_code"] == "E_VALIDATION"

    def test_unknown_tool_returns_e_validation(self, populated_index, db_path, mock_llm, audit_logger):
        """Unknown tool in plan returns E_VALIDATION."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        plan = [{"tool": "nonexistent_tool", "params": {"foo": "bar"}}]
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "unknown-tool-test"}
        response = executor.execute(plan, user)
        assert response.get("error") == "E_VALIDATION"
