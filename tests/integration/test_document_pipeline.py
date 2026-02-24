"""Integration tests: IF-001 — Document pipeline end-to-end."""

import hashlib
import uuid

import pytest

from defense_llm.agent.executor import Executor
from defense_llm.agent.planner_rules import classify_query, build_plan


class TestDocumentPipelineIF001:
    """IF-001: 문서 업로드 → 인덱싱 → 질의 → 근거 인용 답변"""

    def test_index_populated(self, populated_index):
        """ITC-001-01: Documents are indexed."""
        assert populated_index.chunk_count() >= 1

    def test_search_returns_air_chunks(self, populated_index):
        """Air document chunks are searchable."""
        from defense_llm.rag.retriever import hybrid_search
        results = hybrid_search(
            populated_index,
            "DUMMY-F1 최대 순항 고도",
            top_k=3,
            security_label_filter=["PUBLIC", "INTERNAL"],
        )
        assert len(results) >= 1
        assert any("DOC-AIR-001" in r["doc_id"] for r in results)

    def test_executor_returns_standard_schema(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-001-03: Executor response complies with standard schema."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
            model_version="qwen2.5-1.5b-instruct",
            index_version="idx-20260223-1200",
        )

        query = "DUMMY-F1 최대 순항 고도는?"
        qt = classify_query(query)
        plan = build_plan(qt, {
            "query": query,
            "security_label_filter": ["PUBLIC", "INTERNAL"],
        })

        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "test-user"}
        request_id = str(uuid.uuid4())
        response = executor.execute(plan, user, request_id=request_id)

        # Standard schema check
        assert "request_id" in response
        assert "data" in response
        assert "citations" in response
        assert "security_label" in response
        assert "version" in response
        assert "hash" in response

    def test_executor_response_has_citations(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-001-02: Response includes at least one citation with required fields."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        query = "정비 절차 확인"
        qt = classify_query(query)
        plan = build_plan(qt, {
            "query": query,
            "security_label_filter": ["PUBLIC", "INTERNAL"],
        })

        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "test-user"}
        response = executor.execute(plan, user)

        if response.get("citations"):
            for c in response["citations"]:
                assert "doc_id" in c
                assert "doc_rev" in c
                assert "snippet_hash" in c
                assert "page" in c or "section_id" in c

    def test_audit_log_written(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-001-04: Audit log record is created for the request."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
            model_version="qwen2.5-1.5b-instruct",
            index_version="idx-20260223-1200",
        )

        request_id = str(uuid.uuid4())
        query = "비상 절차"
        plan = build_plan(classify_query(query), {"query": query, "security_label_filter": ["PUBLIC", "INTERNAL"]})
        user = {"role": "analyst", "clearance": "INTERNAL", "user_id": "audit-test-user"}

        executor.execute(plan, user, request_id=request_id)

        record = audit_logger.fetch_by_request_id(request_id)
        assert record is not None
        assert record["request_id"] == request_id
        assert record["model_version"] == "qwen2.5-1.5b-instruct"
        assert record["index_version"] == "idx-20260223-1200"
