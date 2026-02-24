"""Rule-based query classifier (UF-030)."""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Pattern


class QueryType(str, Enum):
    STRUCTURED_KB_QUERY = "STRUCTURED_KB_QUERY"
    DOC_RAG_QUERY = "DOC_RAG_QUERY"
    MIXED_QUERY = "MIXED_QUERY"
    SECURITY_RESTRICTED = "SECURITY_RESTRICTED"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Rule definitions — ordered by priority (first match wins for single-type)
# ---------------------------------------------------------------------------

_SECURITY_PATTERNS: List[Pattern] = [
    re.compile(r"기밀|비밀|classified|secret|confidential|주파수.*공개|좌표.*공개", re.IGNORECASE),
    re.compile(r"암호화\s*키|crypto\s*key|encryption\s*key", re.IGNORECASE),
]

_STRUCTURED_PATTERNS: List[Pattern] = [
    re.compile(r"제원|성능|최대\s*(속도|고도|중량|항속|사거리)|최소\s*\w+|탑재\s*(중량|용량)", re.IGNORECASE),
    re.compile(r"호환|compatibility|platform.*spec|weapon.*spec|db.*조회|제한\s*(중량|속도)", re.IGNORECASE),
    re.compile(r"spec(ification)?|weight.*limit|max.*altitude|max.*speed", re.IGNORECASE),
]

_DOC_PATTERNS: List[Pattern] = [
    re.compile(r"문서|교범|절차|매뉴얼|manual|document|procedure|지침|규정|handbook", re.IGNORECASE),
    re.compile(r"찾아|검색|조회|retrieve|search|look.*up|find.*in", re.IGNORECASE),
    re.compile(r"정비|운용|정비절차|maintenance|operation.*manual", re.IGNORECASE),
]


def classify_query(query: str, user_context: dict = None) -> QueryType:
    """Classify a query into one of the defined QueryTypes (UF-030).

    Args:
        query: The user's natural language query.
        user_context: Optional dict with role/clearance (reserved for future use).

    Returns:
        QueryType enum value.
    """
    if not query or not query.strip():
        return QueryType.UNKNOWN

    text = query.strip()

    # Security restriction check — highest priority
    for pat in _SECURITY_PATTERNS:
        if pat.search(text):
            return QueryType.SECURITY_RESTRICTED

    has_structured = any(p.search(text) for p in _STRUCTURED_PATTERNS)
    has_doc = any(p.search(text) for p in _DOC_PATTERNS)

    if has_structured and has_doc:
        return QueryType.MIXED_QUERY
    if has_structured:
        return QueryType.STRUCTURED_KB_QUERY
    if has_doc:
        return QueryType.DOC_RAG_QUERY

    return QueryType.UNKNOWN
