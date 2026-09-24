"""Configuration loading and project paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"


def load_config(base_path: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Load the private config first, then the example config."""
    for name in ("config.json", "config.example.json"):
        path = base_path / name
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                config: dict[str, Any] = json.load(file)
            config["_file"] = name
            return config
    return {"source": "mock"}
