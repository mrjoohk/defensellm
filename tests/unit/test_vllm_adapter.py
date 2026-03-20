"""Tests for VLLMAdapter with mocked openai client.

openai is an optional dependency (not required for offline operation).
All tests here mock sys.modules['openai'] so the suite passes without
a real openai installation.
"""

import json
import sys
from unittest.mock import MagicMock, patch
import types

import pytest

# ---------------------------------------------------------------------------
# Stub the openai module so VLLMAdapter can import without the real package
# ---------------------------------------------------------------------------

_openai_stub = types.ModuleType("openai")
_openai_stub.OpenAI = MagicMock  # will be replaced per-test
sys.modules.setdefault("openai", _openai_stub)

from defense_llm.serving.vllm_adapter import VLLMAdapter  # noqa: E402


def _patch_openai(mock_client_instance):
    """Return a context manager that swaps out openai.OpenAI."""
    mock_cls = MagicMock(return_value=mock_client_instance)
    return patch.object(sys.modules["openai"], "OpenAI", mock_cls), mock_cls


def _make_text_response(content="답변입니다"):
    """Build a mock openai ChatCompletion object for a plain text response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None

    choice = MagicMock()
    choice.message = msg

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def _make_tool_call_response(tool_name="search_docs", args=None):
    """Build a mock openai ChatCompletion object with tool_calls."""
    args = args or {"query": "KF-21"}

    tc = MagicMock()
    tc.id = "call_001"
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(args)

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]

    choice = MagicMock()
    choice.message = msg

    usage = MagicMock()
    usage.prompt_tokens = 15
    usage.completion_tokens = 8

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def test_text_response_no_tools():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_text_response("hello")
    ctx, _ = _patch_openai(client)
    with ctx:
        adapter = VLLMAdapter(model_id="test-model")
        result = adapter.chat([{"role": "user", "content": "hi"}])

    assert result["content"] == "hello"
    assert result["tool_calls"] is None
    assert result["model"] == "test-model"
    assert result["usage"]["prompt_tokens"] == 10


def test_tool_call_response():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_tool_call_response(
        "search_docs", {"query": "KF-21 속도"}
    )
    ctx, _ = _patch_openai(client)
    with ctx:
        adapter = VLLMAdapter(model_id="test-model")
        tools = [{"type": "function", "function": {"name": "search_docs"}}]
        result = adapter.chat([{"role": "user", "content": "q"}], tools=tools)

    assert result["tool_calls"] is not None
    tc = result["tool_calls"][0]
    assert tc["function"]["name"] == "search_docs"
    assert tc["function"]["arguments"] == {"query": "KF-21 속도"}
    assert tc["id"] == "call_001"


def test_tools_passed_to_client():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_text_response()
    ctx, _ = _patch_openai(client)
    with ctx:
        adapter = VLLMAdapter(model_id="m")
        tools = [{"type": "function", "function": {"name": "x"}}]
        adapter.chat([], tools=tools)

    call_kwargs = client.chat.completions.create.call_args[1]
    assert "tools" in call_kwargs
    assert call_kwargs["tool_choice"] == "auto"


def test_no_tools_not_passed_to_client():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_text_response()
    ctx, _ = _patch_openai(client)
    with ctx:
        adapter = VLLMAdapter(model_id="m")
        adapter.chat([])

    call_kwargs = client.chat.completions.create.call_args[1]
    assert "tools" not in call_kwargs


def test_http_error_raises_runtime_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("connection refused")
    ctx, _ = _patch_openai(client)
    with ctx:
        adapter = VLLMAdapter(model_id="m")
        with pytest.raises(RuntimeError, match="E_INTERNAL"):
            adapter.chat([])


def test_model_name_property():
    adapter = VLLMAdapter(model_id="Qwen/Qwen2.5-7B-Instruct")
    assert adapter.model_name == "Qwen/Qwen2.5-7B-Instruct"


def test_default_max_tokens_used():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_text_response()
    ctx, _ = _patch_openai(client)
    with ctx:
        adapter = VLLMAdapter(model_id="m", max_tokens_default=256)
        adapter.chat([], max_tokens=0)

    call_kwargs = client.chat.completions.create.call_args[1]
    assert call_kwargs["max_tokens"] == 256
