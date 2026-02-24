"""Unit tests for knowledge module (UF-010, UF-011, UF-012)."""

import pytest

from defense_llm.knowledge.db_schema import init_db, get_connection
from defense_llm.knowledge.document_meta import register_document, E_VALIDATION, E_CONFLICT
from defense_llm.knowledge.glossary import Glossary


# ---------------------------------------------------------------------------
# UF-010: DB Schema Initialization
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_all_tables(self, tmp_path):
        db = str(tmp_path / "test.db")
        result = init_db(db)
        assert result["success"] is True
        expected_tables = {"schema_version", "documents", "platforms", "weapons", "constraints", "audit_log"}
        assert expected_tables.issubset(set(result["tables_created"]))

    def test_idempotent_double_init(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        result = init_db(db)  # second call must not raise
        assert result["success"] is True

    def test_schema_version_recorded(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        conn = get_connection(db)
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row["version"] == "schema-v1"


# ---------------------------------------------------------------------------
# UF-011: Document Metadata Registration
# ---------------------------------------------------------------------------

_VALID_META = {
    "doc_id": "DOC-001",
    "doc_rev": "v1.0",
    "title": "KF-21 운용 교범 (더미)",
    "field": "air",
    "security_label": "INTERNAL",
    "file_hash": "abc123" * 5 + "ab",
    "page_count": 10,
}


class TestRegisterDocument:
    def test_valid_registration(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        result = register_document(db, _VALID_META)
        assert result["registered"] is True
        assert result["doc_id"] == "DOC-001"

    def test_missing_field_raises_validation(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        bad = {k: v for k, v in _VALID_META.items() if k != "field"}
        with pytest.raises(ValueError, match=E_VALIDATION):
            register_document(db, bad)

    def test_invalid_security_label_raises(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        bad = {**_VALID_META, "security_label": "TOP_SECRET"}
        with pytest.raises(ValueError, match=E_VALIDATION):
            register_document(db, bad)

    def test_invalid_field_raises(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        bad = {**_VALID_META, "field": "space"}
        with pytest.raises(ValueError, match=E_VALIDATION):
            register_document(db, bad)

    def test_duplicate_raises_conflict(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        register_document(db, _VALID_META)
        with pytest.raises(ValueError, match=E_CONFLICT):
            register_document(db, _VALID_META)

    def test_different_rev_is_allowed(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)
        register_document(db, _VALID_META)
        updated = {**_VALID_META, "doc_rev": "v2.0"}
        result = register_document(db, updated)
        assert result["registered"] is True


# ---------------------------------------------------------------------------
# UF-012: Glossary
# ---------------------------------------------------------------------------

class TestGlossary:
    def test_known_term_lookup(self):
        g = Glossary()
        result = g.lookup("KF-21")
        assert result["found"] is True
        assert result["definition"] is not None

    def test_unknown_term_lookup(self):
        g = Glossary()
        result = g.lookup("XYZ-99-NONEXISTENT")
        assert result["found"] is False
        assert result["definition"] is None

    def test_add_and_lookup_custom_term(self):
        g = Glossary()
        g.add("DUMMY-T1", "가상 테스트 무기 체계")
        result = g.lookup("DUMMY-T1")
        assert result["found"] is True
        assert "가상" in result["definition"]

    def test_normalize_text_replaces_acronyms(self):
        g = Glossary()
        text = "KF-21 항공기"
        normalized = g.normalize_text(text)
        assert "KF-21" in normalized
        assert "(" in normalized  # definition appended
