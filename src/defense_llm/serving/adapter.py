"""Abstract LLM adapter interface (UF-060)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


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
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        """Send a chat completion request.

        Args:
            messages: List of { role: "system"|"user"|"assistant"|"tool", content: str }.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            tools: Optional list of OpenAI-format tool definitions. When provided,
                   the LLM may return tool_calls instead of (or in addition to) content.

        Returns:
            dict with keys:
              content (str | None): Text response. None when tool_calls are present.
              tool_calls (list | None): List of tool call dicts when the LLM requests
                  tool execution. Format:
                  [{"id": str, "type": "function",
                    "function": {"name": str, "arguments": dict}}]
                  None when producing a plain text response.
              model (str): Model identifier.
              usage (dict): {"prompt_tokens": int, "completion_tokens": int}

        Raises:
            RuntimeError: (E_INTERNAL) if the adapter call fails.
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""
