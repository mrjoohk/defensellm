"""Document metadata validation and registration (UF-011)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from .db_schema import get_connection

E_VALIDATION = "E_VALIDATION"
E_CONFLICT = "E_CONFLICT"

VALID_FIELDS = {"general", "air", "weapon", "ground", "sensor", "comm"}
VALID_SECURITY_LABELS = {"PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"}


@dataclass
class DocumentMeta:
    doc_id: str
    doc_rev: str
    title: str
    field: str
    security_label: str
    file_hash: str
    page_count: Optional[int] = None


def validate_document_meta(meta: dict) -> DocumentMeta:
    """Validate document metadata dictionary.

    Args:
        meta: Raw metadata dictionary.

    Returns:
        Validated DocumentMeta instance.

    Raises:
        ValueError: (E_VALIDATION) on missing or invalid fields.
    """
    required = ["doc_id", "doc_rev", "title", "field", "security_label", "file_hash"]
    missing = [k for k in required if not meta.get(k)]
    if missing:
        raise ValueError(f"{E_VALIDATION}: Missing required fields: {missing}")

    if meta["field"] not in VALID_FIELDS:
        raise ValueError(
            f"{E_VALIDATION}: Invalid field '{meta['field']}'. Must be one of {VALID_FIELDS}"
        )

    if meta["security_label"] not in VALID_SECURITY_LABELS:
        raise ValueError(
            f"{E_VALIDATION}: Invalid security_label '{meta['security_label']}'. "
            f"Must be one of {VALID_SECURITY_LABELS}"
        )

    return DocumentMeta(
        doc_id=meta["doc_id"],
        doc_rev=meta["doc_rev"],
        title=meta["title"],
        field=meta["field"],
        security_label=meta["security_label"],
        file_hash=meta["file_hash"],
        page_count=meta.get("page_count"),
    )


def register_document(db_path: str, meta: dict) -> dict:
    """Validate and register a document metadata record (UF-011).

    Args:
        db_path: Path to the SQLite database.
        meta: Document metadata dictionary.

    Returns:
        dict with registered=True, doc_id, doc_rev.

    Raises:
        ValueError: E_VALIDATION or E_CONFLICT.
    """
    doc = validate_document_meta(meta)

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM documents WHERE doc_id = ? AND doc_rev = ?",
            (doc.doc_id, doc.doc_rev),
        )
        if cursor.fetchone():
            raise ValueError(
                f"{E_CONFLICT}: Document '{doc.doc_id}' rev '{doc.doc_rev}' already exists."
            )

        cursor.execute(
            """
            INSERT INTO documents (doc_id, doc_rev, title, field, security_label, file_hash, page_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (doc.doc_id, doc.doc_rev, doc.title, doc.field,
             doc.security_label, doc.file_hash, doc.page_count),
        )
        conn.commit()
    finally:
        conn.close()

    return {"registered": True, "doc_id": doc.doc_id, "doc_rev": doc.doc_rev}


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()
