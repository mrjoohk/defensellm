"""Unit tests for config module (UF-001)."""

import os
import pytest

from defense_llm.config.settings import load_config, AppConfig, E_VALIDATION

_BASE_CFG = {
    "model_name": "qwen2.5-1.5b-instruct",
    "db_path": "/tmp/test.db",
    "index_path": "/tmp/index",
    "log_path": "/tmp/logs",
}


class TestLoadConfig:
    def test_valid_config_returns_appconfig(self):
        cfg = load_config(_BASE_CFG, env_override=False)
        assert isinstance(cfg, AppConfig)
        assert cfg.model_name == "qwen2.5-1.5b-instruct"

    def test_defaults_applied(self):
        cfg = load_config(_BASE_CFG, env_override=False)
        assert cfg.security_level == "INTERNAL"
        assert cfg.chunk_max_tokens == 256
        assert cfg.top_k == 5

    def test_missing_model_name_raises(self):
        bad = {k: v for k, v in _BASE_CFG.items() if k != "model_name"}
        with pytest.raises(ValueError, match=E_VALIDATION):
            load_config(bad, env_override=False)

    def test_missing_db_path_raises(self):
        bad = {k: v for k, v in _BASE_CFG.items() if k != "db_path"}
        with pytest.raises(ValueError, match=E_VALIDATION):
            load_config(bad, env_override=False)

    def test_invalid_security_level_raises(self):
        bad = {**_BASE_CFG, "security_level": "TOPSECRET"}
        with pytest.raises(ValueError, match=E_VALIDATION):
            load_config(bad, env_override=False)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("DEFENSE_LLM_MODEL_NAME", "qwen2.5-7b-instruct")
        cfg = load_config(_BASE_CFG, env_override=True)
        assert cfg.model_name == "qwen2.5-7b-instruct"

    def test_custom_security_level(self):
        cfg = load_config({**_BASE_CFG, "security_level": "SECRET"}, env_override=False)
        assert cfg.security_level == "SECRET"
