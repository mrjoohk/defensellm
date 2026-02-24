"""Shared fixtures for integration tests."""

import hashlib
import os
import pytest

from defense_llm.knowledge.db_schema import init_db
from defense_llm.knowledge.document_meta import register_document, compute_file_hash
from defense_llm.rag.chunker import chunk_document
from defense_llm.rag.indexer import DocumentIndex
from defense_llm.audit.logger import AuditLogger
from defense_llm.serving.mock_llm import MockLLMAdapter

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("db") / "test_integration.db")
    init_db(db)
    return db


@pytest.fixture(scope="session")
def mock_llm():
    return MockLLMAdapter(fixed_response="가상 항공기 DUMMY-F1의 최대 순항 고도는 15000m 입니다.")


@pytest.fixture(scope="session")
def audit_logger(db_path):
    return AuditLogger(db_path)


@pytest.fixture(scope="session")
def populated_index(db_path):
    """Index with air and secret dummy documents pre-loaded."""
    index = DocumentIndex()

    # Load air document
    air_doc_path = os.path.join(FIXTURES_DIR, "dummy_doc_air.txt")
    with open(air_doc_path, encoding="utf-8") as f:
        air_text = f.read()

    air_hash = compute_file_hash(air_text.encode())
    register_document(db_path, {
        "doc_id": "DOC-AIR-001",
        "doc_rev": "v1.0",
        "title": "KF-21 DUMMY 운용 교범",
        "field": "air",
        "security_label": "INTERNAL",
        "file_hash": air_hash,
        "page_count": 4,
    })
    air_chunks = chunk_document(
        "DOC-AIR-001", "v1.0", air_text,
        security_label="INTERNAL", doc_field="air"
    )
    index.add_chunks(air_chunks["chunks"])

    # Load secret document
    secret_doc_path = os.path.join(FIXTURES_DIR, "dummy_doc_secret.txt")
    with open(secret_doc_path, encoding="utf-8") as f:
        secret_text = f.read()

    secret_hash = compute_file_hash(secret_text.encode())
    register_document(db_path, {
        "doc_id": "DOC-SECRET-001",
        "doc_rev": "v1.0",
        "title": "SECRET DUMMY DOCUMENT",
        "field": "air",
        "security_label": "SECRET",
        "file_hash": secret_hash,
    })
    secret_chunks = chunk_document(
        "DOC-SECRET-001", "v1.0", secret_text,
        security_label="SECRET", doc_field="air"
    )
    index.add_chunks(secret_chunks["chunks"])

    return index
