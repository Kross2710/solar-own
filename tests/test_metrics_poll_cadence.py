"""Regression tests for the polling-cadence field emitted by ``snapshot()``.

The live-metrics snapshot must expose the polling cadence under the documented
key ``poll_interval_seconds`` while retaining the historical misspelling
``poll_inverval_seconds`` as a backward-compatible alias. The cadence is the
runtime poll interval for local readings and 60 seconds otherwise.

No service startup, vendor request, or hardware is involved: fake providers and
a throwaway SQLite database with synthetic data back the run.
"""
from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.runtime import AppRuntime
from backend.services.collector import snapshot
from providers.base import Metrics, VN_TZ
from providers.evn import EvnTariff
from providers.history import HistoryStore


def _local_metrics() -> Metrics:
    """A local reading carrying cumulative meter counters (triggers meter_today)."""
    return Metrics(
        source="local",
        status="online",
        timestamp=datetime.now(VN_TZ).isoformat(timespec="seconds"),
        meter_total_buy_kwh=100.0,
        meter_total_sell_kwh=5.0,
    )


def _mock_metrics() -> Metrics:
    """A mock reading with no cumulative meter counters."""
    return Metrics(
        source="mock",
        status="online",
        timestamp=datetime.now(VN_TZ).isoformat(timespec="seconds"),
        pv_power_w=1200,
    )


async def _local_get_metrics() -> Metrics:
    return _local_metrics()


async def _mock_get_metrics() -> Metrics:
    return _mock_metrics()


def _provider(metrics_fn: Any, name: str = "mock") -> SimpleNamespace:
    """A fake provider built via SimpleNamespace (no real telemetry)."""

    async def close() -> None:
        return None

    return SimpleNamespace(name=name, get_metrics=metrics_fn, close=close)


class PollCadenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        db_path = Path(self._tmp.name) / "history.db"

        # Synthetic ground-truth: a same-day meter baseline so meter_today()
        # can derive today's buy/sell from the cumulative counters.
        self.store = HistoryStore(db_path)
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT OR REPLACE INTO meter_baseline(day, imp0, exp0) VALUES (?, ?, ?)",
            (datetime.now(VN_TZ).date().isoformat(), 90.0, 0.0),
        )
        con.commit()
        con.close()

        # Same object for live and history so the offline fallback path is not
        # exercised; status is "online" in every scenario below.
        self.runtime = self._make_runtime(_local_get_metrics)

    def _make_runtime(self, metrics_fn: Any) -> AppRuntime:
        provider = _provider(metrics_fn)
        return AppRuntime(
            root=Path("."),
            config={"source": provider.name},
            live_provider=provider,
            history_provider=provider,
            poll_interval=10,
            store=self.store,
            tariff=EvnTariff(),
        )

    def test_local_reading_emits_cadence(self) -> None:
        metrics = asyncio.run(snapshot(self.runtime))

        # Documented key and backward-compatible alias agree on the runtime
        # interval for local readings.
        self.assertEqual(metrics.get("poll_interval_seconds"), 10)
        self.assertEqual(metrics.get("poll_inverval_seconds"), 10)
        # meter_today() derived today's buy/sell from the synthetic baseline.
        self.assertEqual(metrics.get("today_buy_kwh"), 10.0)
        self.assertEqual(metrics.get("today_sell_kwh"), 5.0)

    def test_mock_reading_emits_cadence(self) -> None:
        runtime = self._make_runtime(_mock_get_metrics)
        metrics = asyncio.run(snapshot(runtime))

        # Non-local readings fall back to the fixed 60s cadence.
        self.assertEqual(metrics.get("poll_interval_seconds"), 60)
        self.assertEqual(metrics.get("poll_inverval_seconds"), 60)


if __name__ == "__main__":
    unittest.main()
