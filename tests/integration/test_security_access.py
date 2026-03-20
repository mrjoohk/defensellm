"""Integration tests: IF-003 — Security access control."""

import uuid

import pytest

from defense_llm.agent.executor import Executor
from defense_llm.agent.planner_rules import classify_query, build_plan
from defense_llm.rag.retriever import hybrid_search
from defense_llm.security.rbac import filter_results_by_clearance
from defense_llm.security.masking import mask_output, MASK_TOKEN


class TestSecurityAccessIF003:
    """IF-003: 권한 없는 사용자 → 기밀 문서 결과 0건/거절"""

    def test_public_user_gets_zero_secret_results(self, populated_index):
        """ITC-003-01: PUBLIC user gets no SECRET results."""
        results = hybrid_search(
            populated_index,
            "기밀 가상 내용",
            top_k=10,
            security_label_filter=["PUBLIC"],
        )
        for r in results:
            assert r["security_label"] != "SECRET", (
                f"SECRET document leaked to PUBLIC user: {r['doc_id']}"
            )

    def test_filter_removes_secret_docs_for_public_user(self, populated_index):
        """ITC-003-01 (post-search filter): Filter removes SECRET docs."""
        # Get all results without label filter
        all_results = hybrid_search(populated_index, "테스트", top_k=20)
        public_user = {"role": "guest", "clearance": "PUBLIC"}
        filtered = filter_results_by_clearance(all_results, public_user)

        for r in filtered:
            assert r["security_label"] != "SECRET", (
                f"SECRET document not filtered out: {r['doc_id']}"
            )

    def test_executor_rejects_security_restricted_query(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-003-02: Executor returns E_AUTH for security_restricted plan."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        # security_refusal tool plan
        plan = [{"tool": "security_refusal", "params": {"reason": "보안 제한 질의"}}]
        user = {"role": "guest", "clearance": "PUBLIC", "user_id": "sec-test"}
        response = executor.execute(plan, user)

        assert response.get("error") == "E_AUTH"
        assert response["citations"] == []

    def test_secret_document_content_not_in_public_response(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-003-03: SECRET document content not exposed to PUBLIC user."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        plan = [
            {
                "tool": "search_docs",
                "params": {
                    "query": "기밀 시스템",
                    "top_k": 5,
                    "security_label_filter": ["PUBLIC"],  # only PUBLIC allowed
                },
            }
        ]
        user = {"role": "guest", "clearance": "PUBLIC", "user_id": "public-user"}
        response = executor.execute(plan, user)

        # Verify no SECRET doc_id in citations
        for citation in response.get("citations", []):
            assert citation["doc_id"] != "DOC-SECRET-001", (
                "SECRET document citation leaked to PUBLIC user response"
            )

    def test_masking_applied_to_coordinates(self):
        """ITC-003-04: Output masking removes coordinates."""
        text = "목표 위도 37.1234, 경도 127.5678에 있는 시설"
        result = mask_output(text, mask_rules=["coordinates"])
        assert MASK_TOKEN in result["masked_text"]
        assert "37.1234" not in result["masked_text"]

    def test_audit_log_records_refusal(self, populated_index, db_path, mock_llm, audit_logger):
        """ITC-003-05: Audit log records access refusal."""
        executor = Executor(
            llm_adapter=mock_llm,
            index=populated_index,
            db_path=db_path,
            audit_logger=audit_logger,
        )

        request_id = str(uuid.uuid4())
        plan = [{"tool": "security_refusal", "params": {"reason": "보안 테스트"}}]
        user = {"role": "guest", "clearance": "PUBLIC", "user_id": "refusal-test"}
        executor.execute(plan, user, request_id=request_id)

        record = audit_logger.fetch_by_request_id(request_id)
        assert record is not None
        assert record["error_code"] == "E_AUTH"
