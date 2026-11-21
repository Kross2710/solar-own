import tempfile
from pathlib import Path
from unittest import TestCase

from backend.services.day_ahead import simulate
from providers.history import HistoryStore


class DayAheadTests(TestCase):
    def test_hourly_balance_honors_charge_limit_and_reserve(self):
        # The first load can only drain to the 20% floor. Charging is limited to 3 kW.
        self.assertEqual(simulate([0, 7, 7, 7], [9, 1, 1, 1], 50, 10, 3), [0, 3, 3, 4])

    def test_issue_preserves_first_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db")
            store.day_ahead_snapshot("2026-11-22", {"unused_kwh": 20})
            self.assertEqual(store.day_ahead_snapshot("2026-11-22", {"unused_kwh": 15}), {"unused_kwh": 20})


class ForecastLoopTests(TestCase):
    def test_day_ahead_failure_does_not_prevent_later_yield_refresh(self):
        import asyncio
        import sqlite3
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        from backend.services import forecast

        runtime = SimpleNamespace(
            synced=SimpleNamespace(wait=AsyncMock()),
            latest={"lat": 10, "lon": 106},
            forecaster=SimpleNamespace(ready=True),
            forecast_lock=asyncio.Lock(),
        )
        with (patch.object(forecast, "refresh_forecast", new_callable=AsyncMock) as refresh,
              patch.object(forecast, "build_day_ahead",
                           side_effect=[sqlite3.OperationalError("database is busy"), {}]) as day_ahead,
              patch.object(forecast.asyncio, "sleep", side_effect=[None, asyncio.CancelledError])):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(forecast.forecast_loop(runtime))
        refresh.assert_awaited_once_with(runtime)
        self.assertEqual(day_ahead.await_count, 2)
