"""BM25 + numpy cosine vector index with real embeddings and persistence (P0).

Changes from MVP:
- DocumentIndex now accepts an optional AbstractEmbedder
- VectorIndex stores actual dense numpy vectors (cosine similarity)
- DocumentIndex.save() / load() for index persistence
"""

from __future__ import annotations

import json
import math
import os
import pickle
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np

from .chunker import Chunk

E_INTERNAL = "E_INTERNAL"


# ---------------------------------------------------------------------------
# BM25 (unchanged from MVP)
# ---------------------------------------------------------------------------

class BM25Index:
    """Lightweight BM25 implementation (no external dependencies)."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: List[List[str]] = []
        self._doc_ids: List[str] = []
        self._df: Dict[str, int] = defaultdict(int)
        self._avgdl: float = 0.0
        self._N: int = 0

    def add_documents(self, chunk_ids: List[str], tokenized_docs: List[List[str]]) -> None:
        for cid, tokens in zip(chunk_ids, tokenized_docs):
            self._doc_ids.append(cid)
            self._docs.append(tokens)
            for term in set(tokens):
                self._df[term] += 1
        self._N = len(self._docs)
        self._avgdl = sum(len(d) for d in self._docs) / self._N if self._N else 0.0

    def search(self, query_tokens: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._docs:
            return []
        scores: Dict[str, float] = defaultdict(float)
        for term in query_tokens:
            df = self._df.get(term, 0)
            if df == 0:
                continue
            idf = math.log((self._N - df + 0.5) / (df + 0.5) + 1)
            for i, doc_tokens in enumerate(self._docs):
                tf = doc_tokens.count(term)
                dl = len(doc_tokens)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                scores[self._doc_ids[i]] += idf * (tf * (self.k1 + 1)) / denom
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]


# ---------------------------------------------------------------------------
# Dense vector index — numpy cosine similarity (replaces SimpleVectorIndex)
# ---------------------------------------------------------------------------

class DenseVectorIndex:
    """Cosine similarity index backed by a numpy float32 matrix.

    Replaces the old dict-based TF-IDF index.
    Accepts pre-computed L2-normalised embeddings from AbstractEmbedder,
    so the search is simply a matrix–vector dot product.
    """

    def __init__(self) -> None:
        self._matrix: Optional[np.ndarray] = None   # (N, D)
        self._chunk_ids: List[str] = []

    def add_vectors(self, chunk_ids: List[str], vectors: np.ndarray) -> None:
        """Add pre-computed L2-normalised vectors.

        Args:
            chunk_ids: Corresponding chunk IDs.
            vectors: (N, D) float32 array, L2-normalised.
        """
        assert len(chunk_ids) == vectors.shape[0], "chunk_ids and vectors length mismatch"
        self._chunk_ids.extend(chunk_ids)
        if self._matrix is None:
            self._matrix = vectors.astype(np.float32)
        else:
            self._matrix = np.vstack([self._matrix, vectors.astype(np.float32)])

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        """Return top-k (chunk_id, cosine_score) pairs.

        Args:
            query_vec: (D,) float32 L2-normalised query vector.
            top_k: Number of results.
        """
        if self._matrix is None or len(self._chunk_ids) == 0:
            return []
        scores = self._matrix @ query_vec  # (N,)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self._chunk_ids[i], float(scores[i])) for i in top_indices]

    @property
    def count(self) -> int:
        return len(self._chunk_ids)


# ---------------------------------------------------------------------------
# Legacy SimpleVectorIndex — kept for backward compatibility with tests
# ---------------------------------------------------------------------------

class SimpleVectorIndex:
    """Bag-of-words TF-IDF vector index (kept for backward-compat with MVP tests)."""

    def __init__(self) -> None:
        self._vectors: Dict[str, Dict[str, float]] = {}

    def add(self, chunk_id: str, tokens: List[str]) -> None:
        tf: Dict[str, float] = defaultdict(float)
        for t in tokens:
            tf[t] += 1.0
        total = sum(tf.values()) or 1.0
        self._vectors[chunk_id] = {t: c / total for t, c in tf.items()}

    def search(self, query_tokens: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._vectors:
            return []
        q_tf: Dict[str, float] = defaultdict(float)
        for t in query_tokens:
            q_tf[t] += 1.0
        total = sum(q_tf.values()) or 1.0
        q_vec = {t: c / total for t, c in q_tf.items()}
        scores = [(cid, sum(q_vec.get(t, 0) * w for t, w in vec.items()))
                  for cid, vec in self._vectors.items()]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ---------------------------------------------------------------------------
# DocumentIndex — hybrid BM25 + dense vectors with persistence
# ---------------------------------------------------------------------------

class DocumentIndex:
    """Combined BM25 + dense-vector index with persistence support (UF-020, P0).

    Args:
        embedder: Optional AbstractEmbedder. If None, falls back to legacy
                  SimpleVectorIndex (TF-IDF, suitable for tests).
    """

    def __init__(self, embedder=None) -> None:
        self._embedder = embedder
        self._bm25 = BM25Index()
        self._dense = DenseVectorIndex()
        self._legacy = SimpleVectorIndex()          # fallback when no embedder
        self._meta: Dict[str, dict] = {}
        self.index_version = "idx-00000000-0000"

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: List[Chunk]) -> int:
        """Add chunks to BM25 and vector indexes. Returns count indexed."""
        if not chunks:
            return 0

        chunk_ids = []
        tokenized = []
        texts = []

        for chunk in chunks:
            tokens = chunk.text.lower().split()
            chunk_ids.append(chunk.chunk_id)
            tokenized.append(tokens)
            texts.append(chunk.text)
            self._meta[chunk.chunk_id] = {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "version": getattr(chunk, "version", "v1.0"),
                "page_range": getattr(chunk, "page_range", "unknown"),
                "section_id": getattr(chunk, "section_id", "unknown"),
                "text": chunk.text,
                "security_label": getattr(chunk, "security_label", "INTERNAL"),
                "doc_field": getattr(chunk, "doc_field", "air"),
                "doc_type": getattr(chunk, "doc_type", "unknown"),
                "title": getattr(chunk, "title", ""),
                "system": getattr(chunk, "system", ""),
                "subsystem": getattr(chunk, "subsystem", ""),
                "date": getattr(chunk, "date", ""),
                "language": getattr(chunk, "language", "en"),
                "source_uri": getattr(chunk, "source_uri", ""),
                "section_path": getattr(chunk, "section_path", ""),
            }
            if self._embedder is None:
                self._legacy.add(chunk.chunk_id, tokens)

        if self._embedder is not None:
            # P0: Compute embeddings first for near-deduplication
            vecs = self._embedder.encode(texts)   # (N, D) float32 L2-norm
            
            # Near-dedup: similarity > 0.95 within same field/doc_type
            # We filter chunks before inserting them into BM25/Dense
            filtered_indices = []
            for i, chunk in enumerate(chunks):
                is_duplicate = False
                # Fast check using dense search logic if index already has vectors
                if self._dense._matrix is not None and len(self._dense._chunk_ids) > 0:
                    scores = self._dense._matrix @ vecs[i] # (N,)
                    # Check top hits
                    # Find indices where score > 0.95
                    high_sim_indices = np.where(scores > 0.95)[0]
                    for idx in high_sim_indices:
                        existing_cid = self._dense._chunk_ids[idx]
                        existing_meta = self._meta.get(existing_cid)
                        if existing_meta:
                            # Must match field and doc_type to be considered near dup
                            if (existing_meta.get("doc_field") == chunk.doc_field and 
                                existing_meta.get("doc_type") == chunk.doc_type):
                                is_duplicate = True
                                break
                
                if not is_duplicate:
                    filtered_indices.append(i)

            # Apply filter
            if len(filtered_indices) < len(chunks):
                # We found some duplicates
                chunk_ids = [chunk_ids[i] for i in filtered_indices]
                tokenized = [tokenized[i] for i in filtered_indices]
                vecs = vecs[filtered_indices]
                # Note: self._meta retains the duplicates' metadata but they won't be in BM25 or Dense search
                # Realistically we should delete them from self._meta as well:
                dropped_cids = {chunks[i].chunk_id for i in range(len(chunks)) if i not in filtered_indices}
                for cid in dropped_cids:
                    if cid in self._meta:
                        del self._meta[cid]

            self._dense.add_vectors(chunk_ids, vecs)
            self._bm25.add_documents(chunk_ids, tokenized)
            return len(filtered_indices)
        else:
            self._bm25.add_documents(chunk_ids, tokenized)
            for cid, tokens in zip(chunk_ids, tokenized):
                self._legacy.add(cid, tokens)
            return len(chunks)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        field_filter: Optional[List[str]] = None,
        security_label_filter: Optional[List[str]] = None,
        alpha: float = 0.5,
    ) -> List[dict]:
        """Hybrid BM25 + vector search with metadata filtering.

        If an embedder is configured, uses dense cosine similarity.
        Otherwise falls back to legacy TF-IDF for offline tests.
        """
        tokens = query.lower().split()
        bm25_results = dict(self._bm25.search(tokens, top_k=top_k * 3))

        if self._embedder is not None:
            q_vec = self._embedder.encode([query])[0]    # (D,) float32
            vec_results = dict(self._dense.search(q_vec, top_k=top_k * 3))
        else:
            vec_results = dict(self._legacy.search(tokens, top_k=top_k * 3))

        all_ids = set(bm25_results) | set(vec_results)
        fused: Dict[str, float] = {}
        for cid in all_ids:
            bm25_score = bm25_results.get(cid, 0.0)
            vec_score = vec_results.get(cid, 0.0)
            fused[cid] = alpha * bm25_score + (1 - alpha) * vec_score

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)

        results = []
        for chunk_id, score in ranked:
            meta = self._meta.get(chunk_id)
            if meta is None:
                continue
            if field_filter and meta["doc_field"] not in field_filter:
                continue
            if security_label_filter and meta["security_label"] not in security_label_filter:
                continue
            results.append({**meta, "score": score})
            if len(results) >= top_k:
                break

        return results

    def chunk_count(self) -> int:
        return len(self._meta)

    # ------------------------------------------------------------------
    # Persistence (P0)
    # ------------------------------------------------------------------

    def save(self, index_dir: str) -> None:
        """Persist the full index to disk.

        Creates index_dir if it doesn't exist. Writes:
          - bm25.pkl       — BM25Index
          - dense.pkl      — DenseVectorIndex (numpy matrix included)
          - legacy.pkl     — SimpleVectorIndex fallback
          - meta.json      — chunk metadata

        Args:
            index_dir: Directory to write index files into.
        """
        os.makedirs(index_dir, exist_ok=True)

        with open(os.path.join(index_dir, "bm25.pkl"), "wb") as f:
            pickle.dump(self._bm25, f)

        with open(os.path.join(index_dir, "dense.pkl"), "wb") as f:
            pickle.dump(self._dense, f)

        with open(os.path.join(index_dir, "legacy.pkl"), "wb") as f:
            pickle.dump(self._legacy, f)

        with open(os.path.join(index_dir, "meta.json"), "w", encoding="utf-8") as f:
            out_meta = self._meta.copy()
            if hasattr(self, "index_version"):
                out_meta["index_version"] = self.index_version
            json.dump(out_meta, f, ensure_ascii=False)

    @classmethod
    def load(cls, index_dir: str, embedder=None) -> "DocumentIndex":
        """Load a previously saved index from disk.

        Args:
            index_dir: Directory containing the saved index files.
            embedder: Optional embedder to attach (for future add_chunks calls).

        Returns:
            Populated DocumentIndex instance.

        Raises:
            FileNotFoundError: If index_dir or required files are missing.
        """
        if not os.path.isdir(index_dir):
            raise FileNotFoundError(f"Index directory not found: {index_dir}")

        idx = cls(embedder=embedder)

        with open(os.path.join(index_dir, "bm25.pkl"), "rb") as f:
            idx._bm25 = pickle.load(f)

        with open(os.path.join(index_dir, "dense.pkl"), "rb") as f:
            idx._dense = pickle.load(f)

        with open(os.path.join(index_dir, "legacy.pkl"), "rb") as f:
            idx._legacy = pickle.load(f)

        with open(os.path.join(index_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
            idx.index_version = meta.pop("index_version", "idx-00000000-0000")
            idx._meta = meta

        return idx
