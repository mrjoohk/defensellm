"""Configuration loading and validation (UF-001)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

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
    )
