"""Structured DB schema initialization and migration (UF-010)."""

from __future__ import annotations

import sqlite3
from typing import List

E_INTERNAL = "E_INTERNAL"

SCHEMA_VERSION = "schema-v1"

_DDL_STATEMENTS: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        version     TEXT NOT NULL,
        applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        doc_id          TEXT NOT NULL,
        doc_rev         TEXT NOT NULL,
        title           TEXT NOT NULL,
        field           TEXT NOT NULL,
        security_label  TEXT NOT NULL,
        file_hash       TEXT NOT NULL,
        page_count      INTEGER,
        registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (doc_id, doc_rev)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS platforms (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        platform_id     TEXT UNIQUE NOT NULL,
        name            TEXT NOT NULL,
        field           TEXT NOT NULL,
        max_payload_kg  REAL,
        max_altitude_m  REAL,
        security_label  TEXT NOT NULL DEFAULT 'INTERNAL',
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS weapons (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        weapon_id       TEXT UNIQUE NOT NULL,
        name            TEXT NOT NULL,
        weight_kg       REAL,
        compatible_platforms TEXT,
        security_label  TEXT NOT NULL DEFAULT 'INTERNAL',
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS constraints (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        constraint_id   TEXT UNIQUE NOT NULL,
        platform_id     TEXT,
        weapon_id       TEXT,
        rule_text       TEXT NOT NULL,
        security_label  TEXT NOT NULL DEFAULT 'INTERNAL',
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_id        TEXT UNIQUE NOT NULL,
        request_id      TEXT NOT NULL,
        user_id         TEXT,
        query           TEXT,
        model_version   TEXT,
        index_version   TEXT,
        citations_json  TEXT,
        response_hash   TEXT,
        error_code      TEXT,
        timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
]


def init_db(db_path: str) -> dict:
    """Initialize SQLite DB with all required tables (UF-010).

    Idempotent — safe to call multiple times.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        dict with success flag and list of table names.

    Raises:
        RuntimeError: (E_INTERNAL) on DB connection or SQL errors.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for ddl in _DDL_STATEMENTS:
            cursor.execute(ddl)

        # Record schema version if not already present
        cursor.execute("SELECT COUNT(*) FROM schema_version WHERE version = ?", (SCHEMA_VERSION,))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )

        conn.commit()
        conn.close()

        tables = ["schema_version", "documents", "platforms", "weapons", "constraints", "audit_log"]
        return {"success": True, "tables_created": tables}

    except sqlite3.Error as e:
        raise RuntimeError(f"{E_INTERNAL}: DB initialization failed: {e}") from e


def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
