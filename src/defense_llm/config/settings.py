"""Configuration loading and validation (UF-001)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

# Error codes
E_VALIDATION = "E_VALIDATION"

_REQUIRED_KEYS = ["model_name", "db_path", "index_path", "log_path"]
_VALID_SECURITY_LEVELS = {"PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"}


@dataclass
class AppConfig:
    model_name: str
    db_path: str
    index_path: str
    log_path: str
    security_level: str = "INTERNAL"
    index_version: str = "idx-00000000-0000"
    db_schema_version: str = "schema-v1"
    chunk_max_tokens: int = 256
    chunk_overlap: int = 32
    top_k: int = 5
    # Security toggle (개발 단계에서는 False로 비활성화)
    security_enabled: bool = False
    # Agent loop settings
    agent_mode: bool = False
    max_agent_turns: int = 10
    script_tools_enabled: bool = False
    script_allowed_paths: List[str] = field(default_factory=list)
    # vLLM server settings
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_api_key: str = "EMPTY"


def load_config(config_dict: Optional[dict] = None, env_override: bool = True) -> AppConfig:
    """Load and validate application configuration.

    Args:
        config_dict: Optional base configuration dictionary.
        env_override: If True, environment variables override config_dict values.

    Returns:
        Validated AppConfig instance.

    Raises:
        ValueError: (E_VALIDATION) if required keys are missing or invalid.
    """
    cfg: dict = dict(config_dict or {})

    if env_override:
        env_map = {
            "DEFENSE_LLM_MODEL_NAME": "model_name",
            "DEFENSE_LLM_DB_PATH": "db_path",
            "DEFENSE_LLM_INDEX_PATH": "index_path",
            "DEFENSE_LLM_LOG_PATH": "log_path",
            "DEFENSE_LLM_SECURITY_LEVEL": "security_level",
            "DEFENSE_LLM_INDEX_VERSION": "index_version",
            "DEFENSE_LLM_AGENT_MODE": "agent_mode",
            "DEFENSE_LLM_MAX_AGENT_TURNS": "max_agent_turns",
            "DEFENSE_LLM_SECURITY_ENABLED": "security_enabled",
            "DEFENSE_LLM_SCRIPT_TOOLS_ENABLED": "script_tools_enabled",
            "DEFENSE_LLM_VLLM_BASE_URL": "vllm_base_url",
            "DEFENSE_LLM_VLLM_API_KEY": "vllm_api_key",
        }
        for env_key, cfg_key in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                cfg[cfg_key] = val

    missing = [k for k in _REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        raise ValueError(f"{E_VALIDATION}: Missing required config keys: {missing}")

    security_level = cfg.get("security_level", "INTERNAL")
    if security_level not in _VALID_SECURITY_LEVELS:
        raise ValueError(
            f"{E_VALIDATION}: Invalid security_level '{security_level}'. "
            f"Must be one of {_VALID_SECURITY_LEVELS}"
        )

    def _bool(val: Any, default: bool) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("1", "true", "yes")
        return default

    return AppConfig(
        model_name=cfg["model_name"],
        db_path=cfg["db_path"],
        index_path=cfg["index_path"],
        log_path=cfg["log_path"],
        security_level=security_level,
        index_version=cfg.get("index_version", "idx-00000000-0000"),
        db_schema_version=cfg.get("db_schema_version", "schema-v1"),
        chunk_max_tokens=int(cfg.get("chunk_max_tokens", 256)),
        chunk_overlap=int(cfg.get("chunk_overlap", 32)),
        top_k=int(cfg.get("top_k", 5)),
        agent_mode=_bool(cfg.get("agent_mode", False), False),
        max_agent_turns=int(cfg.get("max_agent_turns", 10)),
        security_enabled=_bool(cfg.get("security_enabled", False), False),
        script_tools_enabled=_bool(cfg.get("script_tools_enabled", False), False),
        script_allowed_paths=cfg.get("script_allowed_paths", []),
        vllm_base_url=cfg.get("vllm_base_url", "http://localhost:8000/v1"),
        vllm_api_key=cfg.get("vllm_api_key", "EMPTY"),
    )
