"""Configuration loading and validation (UF-001)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    # Agent loop settings
    agent_mode: bool = False
    max_agent_turns: int = 10
    script_tools_enabled: bool = False
    script_allowed_paths: List[str] = field(default_factory=list)
    # vLLM server settings
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_api_key: str = "EMPTY"


_CONFIG_FILE_NAME = "config.yaml"


def load_config_file(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Load settings from a YAML config file.

    Searches for config.yaml in the following order:
      1. Explicit path passed as *config_file*
      2. DEFENSE_LLM_CONFIG_FILE environment variable
      3. Project root (4 levels up from this file: src/defense_llm/config/settings.py)

    Returns an empty dict if the file is not found (non-fatal).

    Raises:
        ValueError: (E_VALIDATION) if the file exists but cannot be parsed.
    """
    # Resolve candidate path
    path = config_file or os.environ.get("DEFENSE_LLM_CONFIG_FILE")
    if path is None:
        _here = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
        path = os.path.join(_project_root, _CONFIG_FILE_NAME)

    if not os.path.exists(path):
        return {}

    try:
        import yaml  # pyyaml

        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        raise ValueError(f"{E_VALIDATION}: Failed to parse config file '{path}': {e}") from e


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
        script_tools_enabled=_bool(cfg.get("script_tools_enabled", False), False),
        script_allowed_paths=cfg.get("script_allowed_paths", []),
        vllm_base_url=cfg.get("vllm_base_url", "http://localhost:8000/v1"),
        vllm_api_key=cfg.get("vllm_api_key", "EMPTY"),
    )
