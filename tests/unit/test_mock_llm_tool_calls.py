"""Tests for MockLLMAdapter tool_call_sequence support."""

import pytest
from defense_llm.serving.mock_llm import MockLLMAdapter


_SEARCH_TC = [
    {
        "id": "call_0",
        "type": "function",
        "function": {"name": "search_docs", "arguments": {"query": "KF-21 속도"}},
    }
]


def test_backward_compat_no_sequence():
    """When tool_call_sequence is None, existing text behaviour is preserved."""
    mock = MockLLMAdapter(fixed_response="hello")
    result = mock.chat([{"role": "user", "content": "hi"}])
    assert result["content"] == "hello"
    assert result["tool_calls"] is None
    assert result["model"] == "mock-llm-0.0"


def test_tool_call_on_first_turn():
    mock = MockLLMAdapter(
        fixed_response="최종 답변",
        tool_call_sequence=[_SEARCH_TC, None],
    )
    r0 = mock.chat([{"role": "user", "content": "q"}])
    assert r0["content"] is None
    assert r0["tool_calls"] == _SEARCH_TC

    r1 = mock.chat([{"role": "user", "content": "q"}, {"role": "tool", "content": "{}"}])
    assert r1["content"] == "최종 답변"
    assert r1["tool_calls"] is None


def test_call_count_increments():
    mock = MockLLMAdapter(tool_call_sequence=[_SEARCH_TC, None])
    assert mock.call_count == 0
    mock.chat([])
    assert mock.call_count == 1
    mock.chat([])
    assert mock.call_count == 2


def test_sequence_exhausted_falls_back_to_fixed():
    """After sequence is consumed, fall back to fixed_response."""
    mock = MockLLMAdapter(
        fixed_response="fallback",
        tool_call_sequence=[_SEARCH_TC],
    )
    mock.chat([])   # turn 0 → tool_call
    r1 = mock.chat([])   # turn 1 → beyond sequence → text
    assert r1["content"] == "fallback"
    assert r1["tool_calls"] is None


def test_none_entry_in_sequence_gives_text():
    mock = MockLLMAdapter(
        fixed_response="text answer",
        tool_call_sequence=[None],
    )
    r = mock.chat([{"role": "user", "content": "q"}])
    assert r["content"] == "text answer"
    assert r["tool_calls"] is None


def test_response_fn_returning_dict():
    """response_fn can return a full dict (e.g. with tool_calls)."""
    def fn(msgs):
        return {"content": "dynamic", "tool_calls": None}

    mock = MockLLMAdapter(response_fn=fn)
    r = mock.chat([])
    assert r["content"] == "dynamic"
    assert r["model"] == "mock-llm-0.0"


def test_tools_parameter_accepted():
    """chat() should accept tools param without error."""
    mock = MockLLMAdapter()
    r = mock.chat([], tools=[{"type": "function", "function": {"name": "x"}}])
    assert "content" in r
