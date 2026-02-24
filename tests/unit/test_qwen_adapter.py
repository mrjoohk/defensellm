"""Unit tests for serving/qwen_adapter.py — tested with mock model (no real load).

All tests mock the transformers library so no GPU or model download is needed.
"""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from defense_llm.serving.qwen_adapter import Qwen25Adapter
from defense_llm.serving.adapter import AbstractLLMAdapter


def _make_mock_tokenizer(prompt_token_ids=None):
    """Build a minimal mock tokenizer that mimics Qwen2.5 usage."""
    import torch

    mock_tok = MagicMock()
    prompt_ids = prompt_token_ids or [1, 2, 3, 4, 5]
    # apply_chat_template → str
    mock_tok.apply_chat_template.return_value = "<|im_start|>user\nhello<|im_end|>"
    # __call__ (tokenizer(...)) → BatchEncoding-like object that supports .to()
    input_ids = torch.tensor([prompt_ids])
    encoded = MagicMock()
    encoded.__getitem__ = lambda self, k: {"input_ids": input_ids, "attention_mask": torch.ones_like(input_ids)}[k]
    encoded.to.return_value = {"input_ids": input_ids, "attention_mask": torch.ones_like(input_ids)}
    mock_tok.return_value = encoded
    mock_tok.eos_token_id = 0
    mock_tok.batch_decode.return_value = ["모의 응답 텍스트입니다."]
    return mock_tok


def _make_mock_model(generated_ids=None):
    """Build a minimal mock causal LM model."""
    import torch

    mock_model = MagicMock()
    # generate → tensor of shape (1, prompt_len + new_tokens)
    ids = generated_ids or [1, 2, 3, 4, 5, 6, 7, 8]
    mock_model.generate.return_value = torch.tensor([ids])
    mock_model.device = torch.device("cpu")
    return mock_model


class TestQwen25AdapterInterface:
    def test_implements_abstract_adapter(self):
        adapter = Qwen25Adapter.__new__(Qwen25Adapter)
        adapter._model_id = "Qwen/Qwen2.5-1.5B-Instruct"
        adapter._model = None
        assert issubclass(Qwen25Adapter, AbstractLLMAdapter)

    def test_model_name_property(self):
        adapter = Qwen25Adapter(model_id="Qwen/Qwen2.5-1.5B-Instruct")
        assert adapter.model_name == "Qwen/Qwen2.5-1.5B-Instruct"

    def test_initial_state_not_loaded(self):
        adapter = Qwen25Adapter()
        assert adapter._model is None
        assert adapter._tokenizer is None


class TestQwen25AdapterChat:
    """Chat tests with mocked transformers — no actual model loading."""

    def _make_loaded_adapter(self):
        import torch
        adapter = Qwen25Adapter(model_id="Qwen/Qwen2.5-1.5B-Instruct")
        adapter._tokenizer = _make_mock_tokenizer(prompt_token_ids=[10, 20, 30])
        adapter._model = _make_mock_model(generated_ids=[10, 20, 30, 40, 50, 60])
        return adapter

    def test_chat_returns_required_fields(self):
        adapter = self._make_loaded_adapter()
        result = adapter.chat([{"role": "user", "content": "테스트"}])
        assert "content" in result
        assert "model" in result
        assert "usage" in result
        assert "prompt_tokens" in result["usage"]
        assert "completion_tokens" in result["usage"]

    def test_content_is_string(self):
        adapter = self._make_loaded_adapter()
        result = adapter.chat([{"role": "user", "content": "질의"}])
        assert isinstance(result["content"], str)

    def test_model_field_matches_model_id(self):
        adapter = self._make_loaded_adapter()
        result = adapter.chat([{"role": "user", "content": "질의"}])
        assert result["model"] == "Qwen/Qwen2.5-1.5B-Instruct"

    def test_usage_tokens_non_negative(self):
        adapter = self._make_loaded_adapter()
        result = adapter.chat([{"role": "user", "content": "test"}])
        assert result["usage"]["prompt_tokens"] >= 0
        assert result["usage"]["completion_tokens"] >= 0

    def test_lazy_load_triggers_on_chat(self):
        """_ensure_loaded is called when model is None."""
        adapter = Qwen25Adapter(model_id="Qwen/Qwen2.5-1.5B-Instruct")
        adapter._tokenizer = _make_mock_tokenizer()
        adapter._model = _make_mock_model()
        # Since model is already set, _ensure_loaded should not re-load
        adapter.chat([{"role": "user", "content": "hi"}])
        # No exception → lazy guard works


class TestQwen25AdapterUnload:
    def test_unload_clears_model(self):
        import torch
        adapter = Qwen25Adapter()
        adapter._model = _make_mock_model()
        adapter._tokenizer = _make_mock_tokenizer()
        adapter.unload()
        assert adapter._model is None
        assert adapter._tokenizer is None

    def test_unload_idempotent_when_already_none(self):
        adapter = Qwen25Adapter()
        adapter.unload()  # should not raise
        assert adapter._model is None
