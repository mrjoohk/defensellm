"""Qwen2.5 Transformers LLM Adapter (P0 — production adapter).

Implements AbstractLLMAdapter using HuggingFace transformers.
Supports Qwen2.5-1.5B-Instruct and is interface-compatible with larger models
(7B/14B/32B) — swap model_id in config only.

Design decisions:
- Lazy loading: model is not loaded until first chat() call
- torch_dtype="auto" lets transformers pick bf16 on GPU automatically
- device_map="auto" handles multi-GPU / CPU offload
"""

from __future__ import annotations

import json as _json
import re
import threading
from typing import Any, Dict, List, Optional

from .adapter import AbstractLLMAdapter

E_INTERNAL = "E_INTERNAL"

_DEFAULT_MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
_DEFAULT_SYSTEM_PROMPT = (
    "당신은 방산 도메인 지식 보조 AI입니다. "
    "제공된 근거 자료만을 기반으로 답변하십시오. "
    "근거가 없으면 모른다고 대답하십시오."
)


class Qwen25Adapter(AbstractLLMAdapter):
    """Production LLM adapter using Qwen2.5-Instruct via HuggingFace transformers.

    Args:
        model_id: HuggingFace model ID or local path.
        device_map: "auto" (default) delegates to accelerate for GPU placement.
        torch_dtype: "auto" uses bf16 on CUDA, fp32 on CPU.
        max_new_tokens_default: Default max tokens for generation.
        temperature_default: Default sampling temperature.
        preload: If True, load model immediately (blocking). Default: lazy.
    """

    def __init__(
        self,
        model_id: str = _DEFAULT_MODEL_ID,
        device_map: str = "auto",
        torch_dtype: str = "auto",
        max_new_tokens_default: int = 512,
        temperature_default: float = 0.1,
        preload: bool = False,
    ) -> None:
        self._model_id = model_id
        self._device_map = device_map
        self._torch_dtype = torch_dtype
        self._max_new_tokens_default = max_new_tokens_default
        self._temperature_default = temperature_default

        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()

        if preload:
            self._ensure_loaded()

    @property
    def model_name(self) -> str:
        return self._model_id

    def _ensure_loaded(self) -> None:
        """Lazy-load the model and tokenizer (thread-safe)."""
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                import torch

                self._tokenizer = AutoTokenizer.from_pretrained(self._model_id)
                self._model = AutoModelForCausalLM.from_pretrained(
                    self._model_id,
                    torch_dtype=self._torch_dtype,
                    device_map=self._device_map,
                )
                self._model.eval()
            except Exception as e:
                raise RuntimeError(f"{E_INTERNAL}: Failed to load model '{self._model_id}': {e}") from e

    def _parse_tool_calls(self, content: str) -> Optional[List[Dict[str, Any]]]:
        """Parse Qwen2.5 function-call markers from generated text.

        Supports two formats emitted by Qwen2.5-Instruct:
          Format A (XML):    <tool_call>{"name": "...", "arguments": {...}}</tool_call>
          Format B (tokens): ✿FUNCTION✿name✿ARGS✿{...}✿

        Returns a list of OpenAI-format tool call dicts, or None if none found.
        """
        tool_calls: List[Dict[str, Any]] = []

        # Format A: XML-style markers (newer Qwen2.5)
        pattern_a = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
        for i, m in enumerate(pattern_a.finditer(content)):
            try:
                data = _json.loads(m.group(1))
                tool_calls.append(
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": data.get("name", ""),
                            "arguments": data.get(
                                "arguments", data.get("parameters", {})
                            ),
                        },
                    }
                )
            except (_json.JSONDecodeError, KeyError):
                continue

        # Format B: special-token markers (older Qwen2.5)
        if not tool_calls:
            pattern_b = re.compile(
                r"✿FUNCTION✿(\w+)✿ARGS✿(\{.*?\})✿", re.DOTALL
            )
            for i, m in enumerate(pattern_b.finditer(content)):
                try:
                    tool_calls.append(
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": m.group(1),
                                "arguments": _json.loads(m.group(2)),
                            },
                        }
                    )
                except _json.JSONDecodeError:
                    continue

        return tool_calls if tool_calls else None

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 0,
        temperature: float = -1.0,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        """Generate a response using Qwen2.5-Instruct chat template.

        Args:
            messages: List of { role, content } dicts.
            max_tokens: Max new tokens (0 = use instance default).
            temperature: Sampling temperature (< 0 = use instance default).
            tools: Optional OpenAI-format tool definitions. When provided,
                   the template is rendered with tool context and the response
                   is parsed for tool_call markers.

        Returns:
            {
              content: str | None,
              tool_calls: list | None,
              model: str,
              usage: { prompt_tokens, completion_tokens }
            }
        """
        self._ensure_loaded()

        import torch

        max_new_tokens = max_tokens if max_tokens > 0 else self._max_new_tokens_default
        temp = temperature if temperature >= 0 else self._temperature_default

        # Apply Qwen2.5 chat template (with tools when provided)
        template_kwargs: Dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        if tools:
            template_kwargs["tools"] = tools

        text = self._tokenizer.apply_chat_template(messages, **template_kwargs)
        model_inputs = self._tokenizer([text], return_tensors="pt").to(self._model.device)
        prompt_token_count = model_inputs["input_ids"].shape[1]

        with torch.no_grad():
            generated_ids = self._model.generate(
                **model_inputs,
                max_new_tokens=max_new_tokens,
                temperature=temp if temp > 0 else None,
                do_sample=temp > 0,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        # Strip the prompt tokens from the output
        new_ids = generated_ids[:, prompt_token_count:]
        content = self._tokenizer.batch_decode(new_ids, skip_special_tokens=False)[0].strip()
        completion_token_count = new_ids.shape[1]

        # Parse tool calls when tools were injected
        tool_calls = self._parse_tool_calls(content) if tools else None

        # Strip tool-call markers from content when tool_calls are present
        if tool_calls:
            content_clean = re.sub(r"<tool_call>.*?</tool_call>", "", content, flags=re.DOTALL)
            content_clean = re.sub(r"✿FUNCTION✿.*?✿", "", content_clean, flags=re.DOTALL)
            content_clean = content_clean.strip()
            return {
                "content": content_clean or None,
                "tool_calls": tool_calls,
                "model": self._model_id,
                "usage": {
                    "prompt_tokens": prompt_token_count,
                    "completion_tokens": completion_token_count,
                },
            }

        # Plain text path — strip special tokens manually
        content = self._tokenizer.decode(
            new_ids[0], skip_special_tokens=True
        ).strip()

        return {
            "content": content,
            "tool_calls": None,
            "model": self._model_id,
            "usage": {
                "prompt_tokens": prompt_token_count,
                "completion_tokens": completion_token_count,
            },
        }

    def unload(self) -> None:
        """Release GPU memory by deleting the model."""
        import torch

        with self._lock:
            if self._model is not None:
                del self._model
                self._model = None
            if self._tokenizer is not None:
                del self._tokenizer
                self._tokenizer = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
