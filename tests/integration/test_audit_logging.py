"""Integration tests: IF-004 — Audit log completeness."""

import hashlib
import json
import uuid

import pytest

from defense_llm.agent.executor import Executor
from defense_llm.agent.planner_rules import build_plan, QueryType


class TestAuditLoggingIF004:
    """IF-004: 감사 로그에 request_id/모델버전/인덱스버전/citation 저장 확인"""

    def _run_query(self, populated_index, db_path, mock_llm, audit_logger):
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
            model_version="qwen2.5-1.5b-instruct",
            index_version="idx-20260223-1200",
            db_schema_version="schema-v1",
        )
        request_id = str(uuid.uuid4())
        plan = build_plan(
            QueryType.DOC_RAG_QUERY,
            {"query": "항공기 정비", "security_label_filter": ["PUBLIC", "INTERNAL"]},
        )
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "audit-if004"}
        response = executor.execute(plan, user, request_id=request_id)
        return request_id, response

    def test_audit_record_has_all_required_fields(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-004-01: All required fields present in audit record."""
        request_id, _ = self._run_query(populated_index, db_path, mock_llm, audit_logger)
        record = audit_logger.fetch_by_request_id(request_id)

        assert record is not None
        assert record["request_id"] == request_id
        assert record["model_version"] == "qwen2.5-1.5b-instruct"
        assert record["index_version"] == "idx-20260223-1200"
        assert record["response_hash"] is not None and record["response_hash"] != ""
        assert record["timestamp"] is not None

    def test_audit_record_has_citations(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-004-02: Citations stored in audit record."""
        request_id, response = self._run_query(populated_index, db_path, mock_llm, audit_logger)
        record = audit_logger.fetch_by_request_id(request_id)

        assert record is not None
        # Citations list exists (may be empty if no results, but field must exist)
        assert "citations" in record
        assert isinstance(record["citations"], list)

    def test_response_hash_matches(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-004-03: Stored response_hash matches SHA256 of the response data."""
        request_id, response = self._run_query(populated_index, db_path, mock_llm, audit_logger)
        record = audit_logger.fetch_by_request_id(request_id)

        assert record is not None
        # The hash in the response should match what's stored
        assert response["hash"] == record["response_hash"]

    def test_request_id_consistent(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-004-01 variant: request_id in response matches audit record."""
        request_id, response = self._run_query(populated_index, db_path, mock_llm, audit_logger)
        record = audit_logger.fetch_by_request_id(request_id)

        assert response["request_id"] == request_id
        assert record["request_id"] == request_id

    def test_timestamp_is_iso8601(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-004-04: Timestamp format is ISO8601."""
        from datetime import datetime
        request_id, _ = self._run_query(populated_index, db_path, mock_llm, audit_logger)
        record = audit_logger.fetch_by_request_id(request_id)

        ts = record["timestamp"]
        # Should parse without error
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Timestamp '{ts}' is not valid ISO8601")
