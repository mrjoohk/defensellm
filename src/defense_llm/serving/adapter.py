"""Abstract LLM adapter interface (UF-060)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class AbstractLLMAdapter(ABC):
    """Base interface for all LLM serving adapters.

    Swap implementations to change the underlying model
    (Qwen2.5-1.5B → 7B → 14B → 32B) without changing any other layer.
    """

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> Dict:
        """Send a chat completion request.

        Args:
            messages: List of { role: "system"|"user"|"assistant", content: str }.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            dict: { content: str, model: str, usage: { prompt_tokens: int, completion_tokens: int } }

        Raises:
            RuntimeError: (E_INTERNAL) if the adapter call fails.
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""
