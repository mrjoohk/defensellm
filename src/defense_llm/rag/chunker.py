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
    version: str
    page_range: str
    section_id: str
    text: str
    token_count: int
    security_label: str = "INTERNAL"
    doc_field: str = "air"
    doc_type: str = "unknown"
    title: str = ""
    system: str = ""
    subsystem: str = ""
    date: str = ""
    language: str = "en"
    source_uri: str = ""
    section_path: str = ""


def _simple_tokenize(text: str) -> List[str]:
    """Naive whitespace tokenizer for token counting."""
    return text.split()


def chunk_document(
    doc_id: str,
    version: str,
    text: str,
    security_label: str = "INTERNAL",
    doc_field: str = "air",
    doc_type: str = "unknown",
    title: str = "",
    system: str = "",
    subsystem: str = "",
    date: str = "",
    language: str = "en",
    source_uri: str = "",
    max_tokens: int = 512,
    overlap: int = 64,
) -> dict:
    """Chunk a document into overlapping token windows (UF-020).

    Args:
        doc_id: Document identifier.
        version: Document version.
        text: Full document text.
        security_label: Security classification of document.
        doc_field: Defense domain field (air/weapon/ground/sensor/comm).
        doc_type: Type of document (e.g. spec, glossary).
        title: Title of document.
        system: System metadata.
        subsystem: Subsystem metadata.
        date: Date metadata.
        language: Language metadata.
        source_uri: Source URI metadata.
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

    # Split text into lines, tracking heading state
    lines = text.strip().split("\n")
    chunks: List[Chunk] = []
    page = "1"
    section_counter = 0

    current_h1 = ""
    current_h2 = ""
    current_h3 = ""
    
    current_para_lines = []
    
    def process_paragraph(para_text: str, h1: str, h2: str, h3: str, current_page: str):
        nonlocal section_counter, chunks
        if not para_text.strip():
            return
            
        section_path_parts = [h for h in [h1, h2, h3] if h]
        section_path = " > ".join(section_path_parts) if section_path_parts else ""

        tokens = _simple_tokenize(para_text)
        if not tokens:
            return

        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = " ".join(chunk_tokens)

            section_counter += 1
            section_id = f"sec-{section_counter:04d}"
            
            chunk_id = _make_chunk_id(chunk_text)

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    version=version,
                    page_range=current_page,
                    section_id=section_id,
                    text=chunk_text,
                    token_count=len(chunk_tokens),
                    security_label=security_label,
                    doc_field=doc_field,
                    doc_type=doc_type,
                    title=title,
                    system=system,
                    subsystem=subsystem,
                    date=date,
                    language=language,
                    source_uri=source_uri,
                    section_path=section_path,
                )
            )
            if end >= len(tokens):
                break
            
            # Ensure we always move forward
            next_start = end - overlap
            if next_start <= start:
                next_start = start + 1
            start = next_start

    for line in lines:
        line_strip = line.strip()
        
        # Detect page markers 
        page_match = re.search(r"\[PAGE\s+(\d+)\]|---\s*page\s+(\d+)\s*---", line, re.IGNORECASE)
        if page_match:
            page = str(page_match.group(1) or page_match.group(2))
            line = re.sub(r"\[PAGE\s+\d+\]|---\s*page\s+\d+\s*---", "", line, flags=re.IGNORECASE).strip()
            if not line:
                continue
                
        if line_strip.startswith("### "):
            process_paragraph("\n".join(current_para_lines), current_h1, current_h2, current_h3, page)
            current_para_lines = []
            current_h3 = line_strip[4:].strip()
            # We don't add the heading to paragraph text, just tracking
        elif line_strip.startswith("## "):
            process_paragraph("\n".join(current_para_lines), current_h1, current_h2, current_h3, page)
            current_para_lines = []
            current_h2 = line_strip[3:].strip()
            current_h3 = ""  # Reset lower levels
        elif line_strip.startswith("# "):
            process_paragraph("\n".join(current_para_lines), current_h1, current_h2, current_h3, page)
            current_para_lines = []
            current_h1 = line_strip[2:].strip()
            current_h2 = ""
            current_h3 = ""
        elif line_strip == "":
            process_paragraph("\n".join(current_para_lines), current_h1, current_h2, current_h3, page)
            current_para_lines = []
        else:
            current_para_lines.append(line)
            
    # Process remaining
    process_paragraph("\n".join(current_para_lines), current_h1, current_h2, current_h3, page)
    return {
        "chunks": chunks,
        "indexed_count": len(chunks),
    }


def _make_chunk_id(chunk_text: str) -> str:
    # Exact dedup by taking hash of normalized text
    # Normalization: lower context and condense whitespaces
    normalized = re.sub(r"\s+", " ", chunk_text.lower()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
