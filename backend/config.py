"""Configuration loading and project paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"

# Credential keys mapped to environment variable names.
# Priority: os.environ > .env file > config.json
_CREDENTIAL_ENV = {
    ("cloud", "account"): "SOLAR_CLOUD_ACCOUNT",
    ("cloud", "password"): "SOLAR_CLOUD_PASSWORD",
    ("evn", "portal", "customer_id"): "SOLAR_EVN_CUSTOMER_ID",
    ("evn", "portal", "username"): "SOLAR_EVN_USERNAME",
    ("evn", "portal", "password"): "SOLAR_EVN_PASSWORD",
    ("ai", "api_key"): "SOLAR_GEMINI_API_KEY",
}


def _load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser (no external dependency)."""
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _apply_env_overrides(config: dict[str, Any], env: dict[str, str]) -> None:
    """Override credential fields from env (os.environ wins over .env file)."""
    for path_keys, env_name in _CREDENTIAL_ENV.items():
        value = os.environ.get(env_name) or env.get(env_name)
        if not value:
            continue
        node = config
        for key in path_keys[:-1]:
            node = node.setdefault(key, {})
        node[path_keys[-1]] = value


def load_config(base_path: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Load the private config first, then the example config.

    Real credentials can be provided via environment variables (or a nearby
    ``.env`` file). Resolution priority: os.environ > .env file > config.json.
    """
    for name in ("config.json", "config.example.json"):
        path = base_path / name
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                config: dict[str, Any] = json.load(file)
            config["_file"] = name
            break
    else:
        config = {"source": "mock"}

    _apply_env_overrides(config, _load_dotenv(base_path / ".env"))
    return config
