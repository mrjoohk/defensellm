"""Audit log writer — persists to SQLite audit_log table (UF-050)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional

E_VALIDATION = "E_VALIDATION"
E_INTERNAL = "E_INTERNAL"

_REQUIRED_FIELDS = ["request_id", "model_version", "index_version", "response_hash"]


class AuditLogger:
    """Writes audit records to the SQLite audit_log table (UF-050).

    Args:
        db_path: Path to the SQLite database (must be initialized via init_db).
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def write(
        self,
        request_id: str,
        user_id: str,
        query: str,
        model_version: str,
        index_version: str,
        citations: List[dict],
        response_hash: str,
        error_code: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> dict:
        """Write an audit record (UF-050).

        Args:
            request_id: UUID of the request.
            user_id: Identifier of the requesting user.
            query: The original query or plan string.
            model_version: Model version string.
            index_version: Index version string.
            citations: List of citation dicts included in the response.
            response_hash: SHA-256 hash of the response.
            error_code: Optional error code if the request failed.
            timestamp: Optional ISO8601 timestamp; defaults to UTC now.

        Returns:
            dict: { saved: bool, audit_id: str }

        Raises:
            ValueError: (E_VALIDATION) if required fields are missing.
            RuntimeError: (E_INTERNAL) if DB write fails.
        """
        if not request_id:
            raise ValueError(f"{E_VALIDATION}: request_id is required.")
        if not model_version:
            raise ValueError(f"{E_VALIDATION}: model_version is required.")
        if not index_version:
            raise ValueError(f"{E_VALIDATION}: index_version is required.")
        if response_hash is None:
            raise ValueError(f"{E_VALIDATION}: response_hash is required.")

        audit_id = str(uuid.uuid4())
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        citations_json = json.dumps(citations, ensure_ascii=False)

        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log
                    (audit_id, request_id, user_id, query, model_version,
                     index_version, citations_json, response_hash, error_code, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id, request_id, user_id, query,
                    model_version, index_version,
                    citations_json, response_hash, error_code, ts,
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"{E_INTERNAL}: Audit write failed: {e}") from e

        return {"saved": True, "audit_id": audit_id}

    def fetch(self, audit_id: str) -> Optional[dict]:
        """Retrieve an audit record by audit_id."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_log WHERE audit_id = ?", (audit_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        record = dict(row)
        record["citations"] = json.loads(record.get("citations_json") or "[]")
        return record

    def fetch_by_request_id(self, request_id: str) -> Optional[dict]:
        """Retrieve an audit record by request_id."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audit_log WHERE request_id = ? ORDER BY id DESC LIMIT 1",
            (request_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        record = dict(row)
        record["citations"] = json.loads(record.get("citations_json") or "[]")
        return record
