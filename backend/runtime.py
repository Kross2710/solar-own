"""Application runtime dependencies and mutable state."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request

from backend.config import PROJECT_ROOT, load_config
from backend.provider_factory import build_provider
from providers.assistant import Assistant
from providers.base import Provider
from providers.evn import EvnTariff
from providers.forecast import SolarForecaster
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
    forecaster: SolarForecaster = field(default_factory=SolarForecaster)
    # Weather fetch + training must not overlap (loop vs. first /api/forecast request).
    forecast_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Set after the first history sync, so training does not run on stale data.
    synced: asyncio.Event = field(default_factory=asyncio.Event)
    # The 12 h loop and "Sync now" must not hit SEMS at the same time.
    sync_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_sync: dict[str, Any] | None = None
    assistant: Assistant | None = None

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
        assistant=Assistant(app_config.get("ai")),
    )


def get_runtime(request: Request) -> AppRuntime:
    """FastAPI dependency for the runtime attached by create_app()."""
    return request.app.state.runtime
