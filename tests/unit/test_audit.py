"""Unit tests for audit module — target ≥80% coverage (UF-050)."""

import pytest

from defense_llm.knowledge.db_schema import init_db
from defense_llm.audit.logger import AuditLogger, E_VALIDATION


class TestAuditLogger:
    def test_write_and_fetch_by_audit_id(self, tmp_path):
        db = str(tmp_path / "audit.db")
        init_db(db)
        logger = AuditLogger(db)

        result = logger.write(
            request_id="req-001",
            user_id="user-001",
            query="테스트 질의",
            model_version="qwen2.5-1.5b-instruct",
            index_version="idx-20260223-1200",
            citations=[{"doc_id": "DOC-001", "snippet_hash": "abc123"}],
            response_hash="deadbeef" * 8,
        )
        assert result["saved"] is True
        audit_id = result["audit_id"]

        record = logger.fetch(audit_id)
        assert record is not None
        assert record["request_id"] == "req-001"
        assert record["model_version"] == "qwen2.5-1.5b-instruct"

    def test_fetch_by_request_id(self, tmp_path):
        db = str(tmp_path / "audit.db")
        init_db(db)
        logger = AuditLogger(db)

        logger.write(
            request_id="req-XYZ",
            user_id="u1",
            query="q",
            model_version="m1",
            index_version="idx-001",
            citations=[],
            response_hash="hash123",
        )

        record = logger.fetch_by_request_id("req-XYZ")
        assert record is not None
        assert record["request_id"] == "req-XYZ"

    def test_missing_request_id_raises(self, tmp_path):
        db = str(tmp_path / "audit.db")
        init_db(db)
        logger = AuditLogger(db)
        with pytest.raises(ValueError, match=E_VALIDATION):
            logger.write(
                request_id="",
                user_id="u1",
                query="q",
                model_version="m1",
                index_version="idx-001",
                citations=[],
                response_hash="hash",
            )

    def test_missing_model_version_raises(self, tmp_path):
        db = str(tmp_path / "audit.db")
        init_db(db)
        logger = AuditLogger(db)
        with pytest.raises(ValueError, match=E_VALIDATION):
            logger.write(
                request_id="req-001",
                user_id="u1",
                query="q",
                model_version="",
                index_version="idx-001",
                citations=[],
                response_hash="hash",
            )

    def test_citations_stored_as_list(self, tmp_path):
        db = str(tmp_path / "audit.db")
        init_db(db)
        logger = AuditLogger(db)

        citations = [{"doc_id": "D1", "snippet_hash": "h1"}, {"doc_id": "D2", "snippet_hash": "h2"}]
        res = logger.write(
            request_id="req-002",
            user_id="u1",
            query="q",
            model_version="m",
            index_version="idx",
            citations=citations,
            response_hash="hash",
        )
        record = logger.fetch(res["audit_id"])
        assert len(record["citations"]) == 2

    def test_error_code_stored(self, tmp_path):
        db = str(tmp_path / "audit.db")
        init_db(db)
        logger = AuditLogger(db)

        res = logger.write(
            request_id="req-003",
            user_id="u1",
            query="q",
            model_version="m",
            index_version="idx",
            citations=[],
            response_hash="hash",
            error_code="E_AUTH",
        )
        record = logger.fetch(res["audit_id"])
        assert record["error_code"] == "E_AUTH"

    def test_nonexistent_audit_id_returns_none(self, tmp_path):
        db = str(tmp_path / "audit.db")
        init_db(db)
        logger = AuditLogger(db)
        assert logger.fetch("nonexistent-id") is None
