"""Regression: a strictly OLDER live reading arriving out of order must NOT
overwrite a NEWER stored sample in the same minute.

`HistoryStore.record` used `INSERT OR REPLACE` unconditionally, so a delayed
older live reading (small seconds) arriving AFTER a newer one (large seconds)
in the same minute clobbered the newer sample. This test feeds same-minute
readings out of order into a throwaway SQLite DB and asserts the newest ts
survives.

Each test walks: feed readings for one minute -> assert the newest ts/pv is the
one stored. The out-of-order cases fail by assertion on the original source
(which overwrites) and pass after the fix. Normal newer/equal replacement and
live-supersedes-gap-fill behaviour are preserved and also covered.
"""
import os
import sqlite3
import unittest
from tempfile import TemporaryDirectory

from providers.history import HistoryStore


def _sample(store, minute):
    """Return the samples row for `minute` as a dict (or None)."""
    con = sqlite3.connect(store.path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT minute, ts, pv, load, grid, soc, today FROM samples WHERE minute=?",
            (minute,),
        ).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def _reading(ts, pv=100.0, load=50.0, grid=10.0, soc=80.0, today=5.0):
    return {
        "timestamp": ts,
        "status": "online",
        "pv_power_w": pv,
        "load_power_w": load,
        "grid_power_w": grid,
        "battery_soc": soc,
        "today_energy_kwh": today,
    }


class OutOfOrderMinuteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "history.db")
        self.store = HistoryStore(self.path)
        self.minute = "2026-08-07T23:36"

    def tearDown(self):
        self._tmp.cleanup()

    # ---------- THE BUG: newest live kept when readings arrive out of order ----------
    def test_newest_live_kept_when_arriving_out_of_order(self):
        # Newer live (:45) arrives FIRST, then a delayed older live (:15) arrives AFTER.
        self.store.record(_reading("2026-08-07T23:36:45+07:00", pv=450.0))
        self.store.record(_reading("2026-08-07T23:36:15+07:00", pv=150.0))
        row = _sample(self.store, self.minute)
        self.assertIsNotNone(row)
        self.assertEqual(row["ts"], "2026-08-07T23:36:45+07:00")
        self.assertEqual(row["pv"], 450.0)

    def test_older_reading_cannot_replace_newer(self):
        # Newer first, older second -> the older must NOT overwrite.
        self.store.record(_reading("2026-08-07T23:36:30+07:00", pv=300.0))
        self.store.record(_reading("2026-08-07T23:36:01+07:00", pv=10.0))
        row = _sample(self.store, self.minute)
        self.assertEqual(row["ts"], "2026-08-07T23:36:30+07:00")
        self.assertEqual(row["pv"], 300.0)

    # ---------- normal replacement preserved (pass on original and fixed) ----------
    def test_newer_reading_replaces_older(self):
        # Older first, newer second -> newer replaces (normal behaviour).
        self.store.record(_reading("2026-08-07T23:36:05+07:00", pv=50.0))
        self.store.record(_reading("2026-08-07T23:36:50+07:00", pv=500.0))
        row = _sample(self.store, self.minute)
        self.assertEqual(row["ts"], "2026-08-07T23:36:50+07:00")
        self.assertEqual(row["pv"], 500.0)

    def test_equal_timestamp_replaces(self):
        # Equal timestamp -> normal replacement (idempotent update, not skipped).
        self.store.record(_reading("2026-08-07T23:36:20+07:00", pv=200.0))
        self.store.record(_reading("2026-08-07T23:36:20+07:00", pv=201.0))
        row = _sample(self.store, self.minute)
        self.assertEqual(row["ts"], "2026-08-07T23:36:20+07:00")
        self.assertEqual(row["pv"], 201.0)

    # ---------- live reading still supersedes a gap-fill row ----------
    def test_live_supersedes_gap_fill(self):
        # Gap-fill (:00) first, then live (:33) -> live supersedes gap-fill.
        self.store.backfill_samples(
            "2026-08-07", [{"t": "23:36", "pv": 999.0, "load": 0, "grid": 0, "soc": 0}])
        row = _sample(self.store, self.minute)
        self.assertEqual(row["ts"], "2026-08-07T23:36:00+07:00")
        self.assertEqual(row["pv"], 999.0)
        self.store.record(_reading("2026-08-07T23:36:33+07:00", pv=330.0))
        row = _sample(self.store, self.minute)
        self.assertEqual(row["ts"], "2026-08-07T23:36:33+07:00")
        self.assertEqual(row["pv"], 330.0)

    def test_backfilled_minute_replaced_by_live(self):
        # A backfilled minute (older ts ...:00) replaced by live data (newer ts).
        self.store.backfill_samples("2026-08-07", [{"t": "08:15", "pv": 111.0, "load": 0, "grid": 0, "soc": 0}])
        row = _sample(self.store, "2026-08-07T08:15")
        self.assertEqual(row["ts"], "2026-08-07T08:15:00+07:00")
        self.assertEqual(row["pv"], 111.0)
        self.store.record(_reading("2026-08-07T08:15:42+07:00", pv=420.0))
        row = _sample(self.store, "2026-08-07T08:15")
        self.assertEqual(row["ts"], "2026-08-07T08:15:42+07:00")
        self.assertEqual(row["pv"], 420.0)

    # ---------- minute uniqueness preserved ----------
    def test_minute_uniqueness_preserved(self):
        # Many out-of-order readings still yield exactly one row for the minute.
        for sec in ("05", "50", "12", "33", "01", "45"):
            self.store.record(_reading(f"2026-08-07T23:36:{sec}+07:00", pv=float(sec)))
        con = sqlite3.connect(self.path)
        try:
            n = con.execute(
                "SELECT COUNT(*) FROM samples WHERE minute=?", (self.minute,)
            ).fetchone()[0]
        finally:
            con.close()
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
