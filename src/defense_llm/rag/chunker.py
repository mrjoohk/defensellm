"""Document chunking by section/paragraph (UF-020)."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

E_VALIDATION = "E_VALIDATION"


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_rev: str
    page: int
    section_id: str
    text: str
    token_count: int
    security_label: str = "INTERNAL"
    doc_field: str = "air"


def _simple_tokenize(text: str) -> List[str]:
    """Naive whitespace tokenizer for token counting."""
    return text.split()


def chunk_document(
    doc_id: str,
    doc_rev: str,
    text: str,
    security_label: str = "INTERNAL",
    doc_field: str = "air",
    max_tokens: int = 256,
    overlap: int = 32,
) -> dict:
    """Chunk a document into overlapping token windows (UF-020).

    Args:
        doc_id: Document identifier.
        doc_rev: Document revision.
        text: Full document text.
        security_label: Security classification of document.
        doc_field: Defense domain field (air/weapon/ground/sensor/comm).
        max_tokens: Maximum tokens per chunk.
        overlap: Number of overlapping tokens between adjacent chunks.

    Returns:
        dict with chunks list and indexed_count.

    Raises:
        ValueError: (E_VALIDATION) if text is empty or params invalid.
    """
    if not text or not text.strip():
        raise ValueError(f"{E_VALIDATION}: Document text must not be empty.")
    if max_tokens <= 0:
        raise ValueError(f"{E_VALIDATION}: max_tokens must be positive.")
    if overlap < 0 or overlap >= max_tokens:
        raise ValueError(f"{E_VALIDATION}: overlap must be in [0, max_tokens).")

    # Split on double newlines (paragraph/section boundaries) first
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks: List[Chunk] = []
    page = 1
    section_counter = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Detect page markers like [PAGE 2] or --- page 2 ---
        page_match = re.search(r"\[PAGE\s+(\d+)\]|---\s*page\s+(\d+)\s*---", para, re.IGNORECASE)
        if page_match:
            page = int(page_match.group(1) or page_match.group(2))
            para = re.sub(r"\[PAGE\s+\d+\]|---\s*page\s+\d+\s*---", "", para, flags=re.IGNORECASE).strip()
            if not para:
                continue

        tokens = _simple_tokenize(para)
        if not tokens:
            continue

        # Slide window over tokens
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = " ".join(chunk_tokens)

            section_counter += 1
            section_id = f"sec-{section_counter:04d}"
            chunk_id = _make_chunk_id(doc_id, doc_rev, section_id)

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    doc_rev=doc_rev,
                    page=page,
                    section_id=section_id,
                    text=chunk_text,
                    token_count=len(chunk_tokens),
                    security_label=security_label,
                    doc_field=doc_field,
                )
            )

            if end == len(tokens):
                break
            start = end - overlap

    return {
        "chunks": chunks,
        "indexed_count": len(chunks),
    }


def _make_chunk_id(doc_id: str, doc_rev: str, section_id: str) -> str:
    raw = f"{doc_id}::{doc_rev}::{section_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
