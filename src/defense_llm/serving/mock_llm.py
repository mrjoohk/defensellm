"""Mock LLM adapter for offline testing (UF-060)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .adapter import AbstractLLMAdapter


class MockLLMAdapter(AbstractLLMAdapter):
    """Deterministic mock adapter — no model required.

    Args:
        fixed_response: Static response text returned when no tool_call_sequence
            entry applies.
        response_fn: Optional callable(messages) -> str | dict for dynamic
            responses. If it returns a dict with "tool_calls", those are used
            directly.
        model: Mock model name to report.
        tool_call_sequence: Optional list controlling per-turn behaviour.
            Each element corresponds to one chat() invocation (by call index):
              - None  → produce a text response (fixed_response or response_fn)
              - list  → produce a tool_calls response with that list as tool_calls.
            When call_count exceeds the sequence length, text response is used.
            When tool_call_sequence is None (default), existing behaviour is
            preserved (always returns text) — fully backward-compatible.

    Example::

        mock = MockLLMAdapter(
            fixed_response="최종 답변입니다.",
            tool_call_sequence=[
                # turn 0: LLM requests search_docs
                [{"id": "c0", "type": "function",
                  "function": {"name": "search_docs",
                               "arguments": {"query": "KF-21 속도"}}}],
                # turn 1: LLM produces final text (None → use fixed_response)
                None,
            ],
        )
    """

    def __init__(
        self,
        fixed_response: str = "이것은 테스트 응답입니다.",
        response_fn: Optional[Callable] = None,
        model: str = "mock-llm-0.0",
        tool_call_sequence: Optional[List[Optional[List[dict]]]] = None,
    ) -> None:
        self._fixed_response = fixed_response
        self._response_fn = response_fn
        self._model = model
        self._call_count = 0
        self._tool_call_sequence = tool_call_sequence

    @property
    def model_name(self) -> str:
        return self._model

    def chat(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 512,
        temperature: float = 0.1,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        turn = self._call_count
        self._call_count += 1

        # Check tool_call_sequence for this turn
        if (
            self._tool_call_sequence is not None
            and turn < len(self._tool_call_sequence)
            and self._tool_call_sequence[turn] is not None
        ):
            tc_list = self._tool_call_sequence[turn]
            return {
                "content": None,
                "tool_calls": tc_list,
                "model": self._model,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

        # Text response path
        if self._response_fn is not None:
            raw = self._response_fn(messages)
            # Allow response_fn to return a full dict (e.g. with tool_calls)
            if isinstance(raw, dict):
                raw.setdefault("model", self._model)
                raw.setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0})
                return raw
            content = raw
        else:
            content = self._fixed_response

        # Naive token count estimate (content may be None if caller passes None)
        safe_content = content or ""
        prompt_tokens = sum(
            len((m.get("content") or "").split()) for m in messages
        )
        completion_tokens = len(safe_content.split())

        return {
            "content": content,
            "tool_calls": None,
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
