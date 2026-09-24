"""Application runtime dependencies and mutable state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request

from backend.config import PROJECT_ROOT, load_config
from backend.provider_factory import build_provider
from providers.base import Provider
from providers.evn import EvnTariff
from providers.history import HistoryStore


@dataclass
class AppRuntime:
    root: Path
    config: dict[str, Any]
    live_provider: Provider
    history_provider: Provider
    poll_interval: int
    store: HistoryStore
    tariff: EvnTariff
    latest: dict[str, Any] | None = None
    live_fallback_on: bool = False

    @property
    def history_source(self) -> str | None:
        value = self.config.get("history_source")
        return str(value) if value else None


def create_runtime(
    config: dict[str, Any] | None = None,
    root: Path = PROJECT_ROOT,
) -> AppRuntime:
    app_config = config if config is not None else load_config(root)
    live_provider = build_provider(app_config)
    history_source = app_config.get("history_source")
    history_provider = (
        build_provider(app_config, source=history_source)
        if history_source and history_source != app_config.get("source")
        else live_provider
    )

    # Accept the historical misspelling while preferring the documented key.
    poll_interval = int(
        app_config.get(
            "poll_interval_seconds",
            app_config.get("poll_inverval_seconds", 5),
        )
    )

    return AppRuntime(
        root=root,
        config=app_config,
        live_provider=live_provider,
        history_provider=history_provider,
        poll_interval=poll_interval,
        store=HistoryStore(root / "history.db"),
        tariff=EvnTariff.from_config(app_config.get("evn")),
    )


def get_runtime(request: Request) -> AppRuntime:
    """FastAPI dependency for the runtime attached by create_app()."""
    return request.app.state.runtime
