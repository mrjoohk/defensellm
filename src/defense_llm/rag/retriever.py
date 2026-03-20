"""Hybrid search entry point (UF-021)."""

from __future__ import annotations

from typing import List, Optional

from .indexer import DocumentIndex

E_VALIDATION = "E_VALIDATION"


def hybrid_search(
    index: DocumentIndex,
    query: str,
    top_k: int = 5,
    field_filter: Optional[List[str]] = None,
    security_label_filter: Optional[List[str]] = None,
) -> List[dict]:
    """Execute hybrid BM25 + vector search with metadata filtering (UF-021).

    Args:
        index: DocumentIndex instance.
        query: Natural language search query.
        top_k: Maximum number of results to return.
        field_filter: Optional list of domain fields to restrict search.
        security_label_filter: Optional list of permitted security labels.

    Returns:
        List of result dicts (chunk_id, doc_id, doc_rev, page, section_id, text, score).

    Raises:
        ValueError: (E_VALIDATION) if query is empty.
    """
    if not query or not query.strip():
        raise ValueError(f"{E_VALIDATION}: Search query must not be empty.")

    return index.search(
        query=query,
        top_k=top_k,
        field_filter=field_filter,
        security_label_filter=security_label_filter,
    )
