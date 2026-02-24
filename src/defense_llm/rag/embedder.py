"""Embedding model abstraction + Qwen2.5 mean-pool embedder (P0).

Provides:
- AbstractEmbedder: interface all embedders must implement
- Qwen25Embedder: HuggingFace Qwen2.5 last-hidden-state mean pooling
- TFIDFEmbedder: lightweight bag-of-words fallback (for tests / no-GPU)
"""

from __future__ import annotations

import hashlib
import threading
from abc import ABC, abstractmethod
from typing import List, Optional

import numpy as np

E_INTERNAL = "E_INTERNAL"

_DEFAULT_EMBED_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class AbstractEmbedder(ABC):
    """Shared interface for all embedding backends."""

    @abstractmethod
    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode a list of texts into an L2-normalised float32 matrix.

        Args:
            texts: List of strings to encode.

        Returns:
            numpy array of shape (N, dim), dtype float32, L2-normalised rows.
        """

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimensionality."""


# ---------------------------------------------------------------------------
# Qwen2.5 mean-pool embedder
# ---------------------------------------------------------------------------

class Qwen25Embedder(AbstractEmbedder):
    """Generate embeddings using Qwen2.5 last hidden states with mean pooling.

    Uses the same model weights as the generation adapter — no extra download.
    Mean-pools over non-padding tokens and L2-normalises the result.

    Args:
        model_id: HuggingFace model ID or local path.
        device: "cuda", "cpu", or None (auto-detect).
        batch_size: Number of texts per forward pass.
        max_length: Tokenizer max length for truncation.
        preload: If True, load model immediately.
    """

    def __init__(
        self,
        model_id: str = _DEFAULT_EMBED_MODEL,
        device: Optional[str] = None,
        batch_size: int = 8,
        max_length: int = 512,
        preload: bool = False,
    ) -> None:
        self._model_id = model_id
        self._batch_size = batch_size
        self._max_length = max_length
        self._model = None
        self._tokenizer = None
        self._device = device
        self._lock = threading.Lock()
        self._dim: Optional[int] = None

        if preload:
            self._ensure_loaded()

    @property
    def dim(self) -> int:
        self._ensure_loaded()
        return self._dim

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer

                if self._device is None:
                    self._device = "cuda" if torch.cuda.is_available() else "cpu"

                self._tokenizer = AutoTokenizer.from_pretrained(self._model_id)
                self._model = AutoModel.from_pretrained(
                    self._model_id,
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                )
                self._model.to(self._device)
                self._model.eval()
                # probe dim
                self._dim = self._model.config.hidden_size
            except Exception as e:
                raise RuntimeError(
                    f"{E_INTERNAL}: Failed to load embedding model '{self._model_id}': {e}"
                ) from e

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts to L2-normalised float32 embeddings."""
        self._ensure_loaded()
        import torch

        all_vecs: List[np.ndarray] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            encoded = {k: v.to(self._device) for k, v in encoded.items()}
            with torch.no_grad():
                out = self._model(**encoded)
            # Mean-pool over non-padding tokens
            hidden = out.last_hidden_state  # (B, L, D)
            mask = encoded["attention_mask"].unsqueeze(-1).float()  # (B, L, 1)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)  # (B, D)
            all_vecs.append(pooled.float().cpu().numpy())

        matrix = np.vstack(all_vecs).astype(np.float32)
        # L2 normalise
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return matrix / norms


# ---------------------------------------------------------------------------
# TFIDF fallback embedder (offline tests, no GPU required)
# ---------------------------------------------------------------------------

class TFIDFEmbedder(AbstractEmbedder):
    """Bag-of-words TF-IDF embedder — deterministic, no model needed.

    Vocabulary is built lazily on first encode() call or explicitly via fit().
    Uses a fixed vocabulary size to ensure consistent dimensionality.

    Suitable for unit tests and offline environments.
    """

    def __init__(self, vocab_size: int = 1024) -> None:
        self._vocab_size = vocab_size
        self._vocab: dict[str, int] = {}
        self._idf: Optional[np.ndarray] = None
        self._fitted = False

    @property
    def dim(self) -> int:
        return self._vocab_size

    def fit(self, texts: List[str]) -> "TFIDFEmbedder":
        """Build vocabulary and IDF weights from a corpus."""
        from collections import Counter, defaultdict
        import math

        # Tokenize
        tokenized = [t.lower().split() for t in texts]

        # Build vocabulary (top vocab_size by frequency)
        all_tokens = [tok for doc in tokenized for tok in doc]
        freq = Counter(all_tokens)
        top_tokens = [tok for tok, _ in freq.most_common(self._vocab_size)]
        self._vocab = {tok: i for i, tok in enumerate(top_tokens)}

        # IDF
        N = len(texts)
        df = defaultdict(int)
        for doc in tokenized:
            for tok in set(doc):
                if tok in self._vocab:
                    df[tok] += 1
        idf = np.zeros(self._vocab_size, dtype=np.float32)
        for tok, idx in self._vocab.items():
            idf[idx] = math.log((N + 1) / (df.get(tok, 0) + 1)) + 1.0
        self._idf = idf
        self._fitted = True
        return self

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts using TF-IDF vectors (auto-fits if needed)."""
        if not self._fitted:
            self.fit(texts)

        matrix = np.zeros((len(texts), self._vocab_size), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = text.lower().split()
            from collections import Counter
            tf = Counter(tokens)
            total = len(tokens) or 1
            for tok, count in tf.items():
                idx = self._vocab.get(tok)
                if idx is not None:
                    matrix[i, idx] = (count / total) * (self._idf[idx] if self._idf is not None else 1.0)

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return matrix / norms
