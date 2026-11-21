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
