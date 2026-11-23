"""Regression: backfill_samples must skip invalid clock strings (e.g. "25:00",
"AA:BB") and invalid calendar days, while still storing valid HH:MM / HH:MM:SS
minutes. Uses a throwaway SQLite file so no live data is touched.

Each test walks: feed a mix of valid and invalid points -> assert only the valid
minutes land in `samples`. The invalid-clock / invalid-day cases fail by
assertion on the original source (which only checked length + colon) and pass
after the fix.
"""
import os
import sqlite3
import unittest
from tempfile import TemporaryDirectory

from providers.history import HistoryStore


class BackfillSampleClockTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "history.db")
        self.store = HistoryStore(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def _minutes(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute(
            "SELECT minute, pv, load, grid, soc FROM samples ORDER BY minute")]
        con.close()
        return {r["minute"]: r for r in rows}

    def _point(self, t, pv=10, load=20, grid=0, soc=50):
        return {"t": t, "pv": pv, "load": load, "grid": grid, "soc": soc}

    # ---------- valid boundaries (must pass on original and fixed) ----------
    def test_valid_midnight_and_end_of_day(self):
        n = self.store.backfill_samples("2026-08-07", [
            self._point("00:00", pv=1, load=2, soc=50),
            self._point("23:59", pv=3, load=4, soc=55),
        ])
        mins = self._minutes()
        self.assertIn("2026-08-07T00:00", mins)
        self.assertIn("2026-08-07T23:59", mins)
        self.assertEqual(n, 2)

    def test_valid_leap_day_is_stored(self):
        # Feb 29 exists in a leap year -> must NOT be rejected by calendar check.
        n = self.store.backfill_samples("2024-02-29", [self._point("06:00")])
        mins = self._minutes()
        self.assertIn("2024-02-29T06:00", mins)
        self.assertEqual(n, 1)

    # ---------- invalid hours (regression) ----------
    def test_invalid_hours_are_skipped(self):
        n = self.store.backfill_samples("2026-08-07", [
            self._point("25:00"),
            self._point("24:00"),
            self._point("99:99"),
            self._point("12:30", pv=7, load=8, soc=60),  # valid, same response
        ])
        mins = self._minutes()
        self.assertNotIn("2026-08-07T25:00", mins)
        self.assertNotIn("2026-08-07T24:00", mins)
        self.assertNotIn("2026-08-07T99:99", mins)
        self.assertIn("2026-08-07T12:30", mins)  # valid point not lost
        self.assertEqual(n, 1)

    # ---------- invalid minutes / non-numeric (regression) ----------
    def test_invalid_minutes_and_garbage_are_skipped(self):
        n = self.store.backfill_samples("2026-08-07", [
            self._point("12:60"),
            self._point("AA:BB"),
            self._point("12:99"),
            self._point("09:15", pv=5, load=6, soc=65),  # valid
        ])
        mins = self._minutes()
        self.assertNotIn("2026-08-07T12:60", mins)
        self.assertNotIn("2026-08-07TAA:BB", mins)
        self.assertNotIn("2026-08-07T12:99", mins)
        self.assertIn("2026-08-07T09:15", mins)
        self.assertEqual(n, 1)

    # ---------- invalid calendar days (regression) ----------
    def test_invalid_calendar_day_is_skipped(self):
        # Feb 30 does not exist.
        n = self.store.backfill_samples("2026-02-30", [self._point("10:00")])
        self.assertEqual(n, 0)
        self.assertEqual(self._minutes(), {})

    def test_invalid_month_is_skipped(self):
        n = self.store.backfill_samples("2026-13-01", [self._point("10:00")])
        self.assertEqual(n, 0)
        self.assertEqual(self._minutes(), {})

    def test_invalid_day_of_month_is_skipped(self):
        # April has 30 days.
        n = self.store.backfill_samples("2026-04-31", [self._point("10:00")])
        self.assertEqual(n, 0)
        self.assertEqual(self._minutes(), {})

    # ---------- HH:MM:SS stores the minute (must pass on original and fixed) ----------
    def test_hhmmss_stores_minute(self):
        n = self.store.backfill_samples("2026-08-07", [
            self._point("14:23:45", pv=12, load=13, soc=70),
        ])
        mins = self._minutes()
        self.assertIn("2026-08-07T14:23", mins)
        self.assertNotIn("2026-08-07T14:23:45", mins)
        self.assertEqual(n, 1)

    def test_invalid_clock_suffix_and_seconds_are_skipped(self):
        inserted = self.store.backfill_samples("2026-08-07", [
            self._point("12:34junk"),
            self._point("12:35:60"),
            self._point("12:36:5"),
            self._point("12:37:59"),
        ])

        self.assertEqual(inserted, 1)
        self.assertEqual(set(self._minutes()), {"2026-08-07T12:37"})

    def test_only_canonical_calendar_days_are_accepted(self):
        for day in ("20260807", "2026-W32-5", "2026-08-07junk"):
            with self.subTest(day=day):
                self.assertEqual(self.store.backfill_samples(day, [self._point("14:23")]), 0)

        self.assertEqual(self._minutes(), {})

    # ---------- duplicate minute keeps existing (live) reading ----------
    def test_duplicate_minute_keeps_live_reading(self):
        con = sqlite3.connect(self.path)
        con.execute(
            "INSERT INTO samples(minute, ts, pv, load, grid, soc) VALUES (?,?,?,?,?,?)",
            ("2026-08-07T12:30", "2026-08-07T12:30:00+07:00", 999, 999, 999, 999))
        con.commit()
        con.close()
        n = self.store.backfill_samples("2026-08-07", [self._point("12:30", pv=10)])
        mins = self._minutes()
        self.assertEqual(mins["2026-08-07T12:30"]["pv"], 999)  # live reading preserved
        self.assertEqual(n, 0)  # nothing new inserted

    # ---------- all-null point skipped ----------
    def test_all_null_point_skipped(self):
        n = self.store.backfill_samples("2026-08-07", [
            {"t": "10:00", "pv": None, "load": None, "grid": None, "soc": None},
        ])
        self.assertEqual(n, 0)
        self.assertEqual(self._minutes(), {})

    # ---------- empty points / missing "t" ----------
    def test_empty_points_and_missing_t(self):
        self.assertEqual(self.store.backfill_samples("2026-08-07", []), 0)
        n = self.store.backfill_samples("2026-08-07", [
            {"pv": 1, "load": 2, "grid": 0, "soc": 50},  # no "t" key
        ])
        self.assertEqual(n, 0)
        self.assertEqual(self._minutes(), {})


if __name__ == "__main__":
    unittest.main()
