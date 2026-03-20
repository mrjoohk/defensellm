"""Unit tests for serving module (UF-060)."""

import pytest

from defense_llm.serving.mock_llm import MockLLMAdapter
from defense_llm.serving.adapter import AbstractLLMAdapter


class TestMockLLMAdapter:
    def test_returns_fixed_response(self):
        adapter = MockLLMAdapter(fixed_response="고정 응답")
        result = adapter.chat([{"role": "user", "content": "안녕"}])
        assert result["content"] == "고정 응답"

    def test_response_has_required_fields(self):
        adapter = MockLLMAdapter()
        result = adapter.chat([{"role": "user", "content": "테스트"}])
        assert "content" in result
        assert "model" in result
        assert "usage" in result
        assert "prompt_tokens" in result["usage"]
        assert "completion_tokens" in result["usage"]

    def test_usage_tokens_non_negative(self):
        adapter = MockLLMAdapter()
        result = adapter.chat([{"role": "user", "content": "테스트"}])
        assert result["usage"]["prompt_tokens"] >= 0
        assert result["usage"]["completion_tokens"] >= 0

    def test_model_name_property(self):
        adapter = MockLLMAdapter(model="test-model-1.0")
        assert adapter.model_name == "test-model-1.0"

    def test_call_count_increments(self):
        adapter = MockLLMAdapter()
        assert adapter.call_count == 0
        adapter.chat([{"role": "user", "content": "q1"}])
        adapter.chat([{"role": "user", "content": "q2"}])
        assert adapter.call_count == 2

    def test_custom_response_fn(self):
        def echo_fn(messages):
            return "ECHO: " + messages[-1]["content"]

        adapter = MockLLMAdapter(response_fn=echo_fn)
        result = adapter.chat([{"role": "user", "content": "hello"}])
        assert result["content"] == "ECHO: hello"

    def test_implements_abstract_adapter(self):
        adapter = MockLLMAdapter()
        assert isinstance(adapter, AbstractLLMAdapter)
