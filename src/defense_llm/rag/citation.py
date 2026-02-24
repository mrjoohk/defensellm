"""Citation packaging from search results (UF-022)."""

from __future__ import annotations

import hashlib
from typing import List

E_VALIDATION = "E_VALIDATION"

_REQUIRED_CHUNK_FIELDS = {"doc_id", "doc_rev", "text"}


def package_citations(chunks: List[dict]) -> List[dict]:
    """Package search result chunks into citation records (UF-022).

    Each citation includes doc_id, doc_rev, page (or section_id), snippet, snippet_hash.

    Args:
        chunks: List of search result dicts from hybrid_search.

    Returns:
        List of citation dicts.

    Raises:
        ValueError: (E_VALIDATION) if a chunk is missing required fields.
    """
    citations = []
    for chunk in chunks:
        missing = _REQUIRED_CHUNK_FIELDS - set(chunk.keys())
        if missing:
            raise ValueError(
                f"{E_VALIDATION}: Chunk missing required fields: {missing}"
            )

        snippet = chunk["text"][:300]  # cap snippet length
        snippet_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

        citations.append({
            "doc_id": chunk["doc_id"],
            "doc_rev": chunk["doc_rev"],
            "page": chunk.get("page", 1),
            "section_id": chunk.get("section_id"),
            "title": chunk.get("title"),
            "snippet": snippet,
            "snippet_hash": snippet_hash,
        })

    return citations
