"""Audit record data schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AuditRecord:
    audit_id: str
    request_id: str
    user_id: str
    query: str
    model_version: str
    index_version: str
    citations: List[dict]
    response_hash: str
    timestamp: str
    error_code: Optional[str] = None
