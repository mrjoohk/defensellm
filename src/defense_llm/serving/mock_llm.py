"""Mock LLM adapter for offline testing (UF-060)."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .adapter import AbstractLLMAdapter


class MockLLMAdapter(AbstractLLMAdapter):
    """Deterministic mock adapter — no model required.

    Args:
        fixed_response: Static response text returned for every call.
        response_fn: Optional callable(messages) -> str for dynamic responses.
        model: Mock model name to report.
    """

    def __init__(
        self,
        fixed_response: str = "이것은 테스트 응답입니다.",
        response_fn: Optional[Callable] = None,
        model: str = "mock-llm-0.0",
    ) -> None:
        self._fixed_response = fixed_response
        self._response_fn = response_fn
        self._model = model
        self._call_count = 0

    @property
    def model_name(self) -> str:
        return self._model

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> Dict:
        self._call_count += 1

        if self._response_fn is not None:
            content = self._response_fn(messages)
        else:
            content = self._fixed_response

        # Naive token count estimate
        prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)
        completion_tokens = len(content.split())

        return {
            "content": content,
            "model": self._model,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }

    @property
    def call_count(self) -> int:
        """Number of times chat() has been called (useful for assertions)."""
        return self._call_count
