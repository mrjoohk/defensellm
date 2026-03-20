"""Integration tests: IF-002 — Structured KB query."""

import uuid
import pytest

from defense_llm.agent.executor import Executor
from defense_llm.agent.planner_rules import classify_query, build_plan, QueryType
from defense_llm.knowledge.db_schema import get_connection


def _insert_dummy_platform(db_path: str):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO platforms (platform_id, name, field, max_payload_kg, max_altitude_m, security_label)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("DUMMY-A1", "가상 전술 항공기 A1", "air", 7000.0, 15000.0, "INTERNAL"),
    )
    conn.commit()
    conn.close()


class TestKBQueryIF002:
    """IF-002: 정형 DB 제원 조회 → 응답"""

    def test_planner_classifies_structured_query(self):
        """ITC-002-01: STRUCTURED_KB_QUERY classification."""
        query = "DUMMY-A1 플랫폼의 최대 탑재 중량은?"
        qt = classify_query(query)
        assert qt in (QueryType.STRUCTURED_KB_QUERY, QueryType.MIXED_QUERY)

    def test_executor_db_query_returns_response(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-002-02: Executor queries DB and returns response."""
        _insert_dummy_platform(db_path)

        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        query = "DUMMY-A1"
        plan = build_plan(
            QueryType.STRUCTURED_KB_QUERY,
            {"query": query, "security_label_filter": ["PUBLIC", "INTERNAL"]},
        )

        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "kb-test"}
        response = executor.execute(plan, user)

        assert "data" in response
        assert "answer" in response["data"]

    def test_audit_logged_for_kb_query(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-002-04: Audit log saved for KB query."""
        _insert_dummy_platform(db_path)

        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
            model_version="qwen2.5-1.5b-instruct",
            index_version="idx-20260223-1200",
        )

        request_id = str(uuid.uuid4())
        plan = build_plan(
            QueryType.STRUCTURED_KB_QUERY,
            {"query": "DUMMY-A1", "security_label_filter": ["PUBLIC", "INTERNAL"]},
        )
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "kb-audit-test"}
        executor.execute(plan, user, request_id=request_id)

        record = audit_logger.fetch_by_request_id(request_id)
        assert record is not None
        assert record["request_id"] == request_id
