"""vLLM LLM Adapter — OpenAI-compatible HTTP client targeting a vLLM server.

Usage
-----
1. Start a vLLM server (on the inference host)::

       vllm serve Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 8000

2. Instantiate the adapter pointing at that server::

       from defense_llm.serving.vllm_adapter import VLLMAdapter
       adapter = VLLMAdapter(model_id="Qwen/Qwen2.5-7B-Instruct",
                             base_url="http://localhost:8000/v1")

3. Drop it in anywhere AbstractLLMAdapter is expected — the executor, eval
   runner, etc. all work without modification.

Design decisions
----------------
- Uses the ``openai`` Python client (already a common dependency in LLM projects).
  The ``api_key`` defaults to ``"EMPTY"`` — vLLM does not require one.
- Native tool_calls support via OpenAI format (vLLM passes them through).
- All ``openai`` exceptions are caught and re-raised as ``RuntimeError(E_INTERNAL)``.
- Connection to the server is created per-call to avoid holding a persistent
  connection across process restarts; this is fast because the openai client
  is lightweight.
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict, List, Optional

from .adapter import AbstractLLMAdapter

E_INTERNAL = "E_INTERNAL"


class VLLMAdapter(AbstractLLMAdapter):
    """LLM adapter that calls a running vLLM OpenAI-compatible server.

    Args:
        model_id: Model name as served by vLLM (must match ``--model`` arg).
        base_url: HTTP base URL of the vLLM server (default: http://localhost:8000/v1).
        api_key: API key sent in the Authorization header. vLLM defaults to "EMPTY".
        max_tokens_default: Default max_tokens when caller passes 0 or omits.
        temperature_default: Default temperature when caller passes a negative value.
        timeout: HTTP request timeout in seconds (default: 60).
    """

    def __init__(
        self,
        model_id: str,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        max_tokens_default: int = 512,
        temperature_default: float = 0.1,
        timeout: float = 60.0,
    ) -> None:
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._max_tokens_default = max_tokens_default
        self._temperature_default = temperature_default
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model_id

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 0,
        temperature: float = -1.0,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        """Send a chat completion request to the vLLM server.

        Args:
            messages: Conversation history in OpenAI message format.
            max_tokens: Max new tokens (0 = use instance default).
            temperature: Sampling temperature (< 0 = use instance default).
            tools: Optional OpenAI-format tool definitions. When provided,
                   tool_choice is set to "auto".

        Returns:
            {
              content: str | None,
              tool_calls: list | None,
              model: str,
              usage: {prompt_tokens: int, completion_tokens: int}
            }

        Raises:
            RuntimeError: (E_INTERNAL) wrapping any openai or HTTP error.
        """
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                f"{E_INTERNAL}: 'openai' package is required for VLLMAdapter. "
                "Install it with: pip install openai"
            ) from exc

        resolved_max_tokens = max_tokens if max_tokens > 0 else self._max_tokens_default
        resolved_temp = temperature if temperature >= 0 else self._temperature_default

        kwargs: Dict[str, Any] = {
            "model": self._model_id,
            "messages": messages,
            "max_tokens": resolved_max_tokens,
            "temperature": resolved_temp,
            "timeout": self._timeout,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            client = OpenAI(base_url=self._base_url, api_key=self._api_key)
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"{E_INTERNAL}: vLLM request failed: {exc}") from exc

        choice = response.choices[0]
        msg = choice.message

        # Parse tool_calls from OpenAI response format
        tool_calls: Optional[List[Dict[str, Any]]] = None
        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                try:
                    arguments = _json.loads(tc.function.arguments)
                except (_json.JSONDecodeError, AttributeError):
                    arguments = {}
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": arguments,
                        },
                    }
                )

        usage = response.usage
        return {
            "content": msg.content,
            "tool_calls": tool_calls,
            "model": self._model_id,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
            },
        }
