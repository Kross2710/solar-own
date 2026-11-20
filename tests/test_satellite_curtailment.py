from unittest import TestCase

from tools.research.satellite_curtailment import estimate


class SatelliteCurtailmentTests(TestCase):
    def test_later_load_step_only_adds_its_own_interval(self):
        low = dict(pv=839, load=834, batt=5, soc=100, grid=0)
        high = dict(low, pv=3572, load=3572)
        morning = [(500, [low, low])] * 12
        later = [(500, [high, high])]
        before = estimate(morning, 10, 16)["covered_loss_kwh"]
        after = estimate(morning + later, 10, 16)["covered_loss_kwh"]
        self.assertAlmostEqual(after - before, (5000 - 3572) / 6000, places=2)

    def test_missing_radiation_produces_no_energy_estimate(self):
        p = dict(pv=900, load=900, batt=0, soc=100, grid=0)
        result = estimate([(None, [p, p])], 10, 16)
        self.assertIsNone(result["covered_loss_kwh"])
        self.assertEqual(result["missing_minutes"], 10)


class SatelliteHistoryTests(TestCase):
    def test_history_keeps_legacy_estimates_out_of_satellite_totals(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from providers.history import HistoryStore

        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            legacy = HistoryStore(path)
            legacy.record_curtailment("2026-11-19", 22.4, "10:30")

            satellite_store = HistoryStore(path, satellite_curtailment=True)
            satellite_store.record_satellite_gain("2026-11-19", 11.96)
            self.assertEqual(satellite_store.curtailment_recent(), [])
            self.assertEqual(satellite_store.curtailment_days(), set())

            satellite_store.record_curtailment("2026-11-19", 38.8, "10:30")
            self.assertEqual(satellite_store.curtailment_recent()[0]["lost"], 38.8)
            self.assertEqual(legacy.curtailment_recent()[0]["lost"], 22.4)
            self.assertEqual(satellite_store.satellite_gains("2026-11-01", "2026-11-20"),
                             {"2026-11-19": 11.96})


class SatelliteBackfillTests(TestCase):
    def test_failed_day_is_retried_after_later_days_are_saved(self):
        import asyncio
        from datetime import datetime, timedelta
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        from backend.services import curtailment
        from providers.base import VN_TZ
        from providers.history import HistoryStore

        today = datetime.now(VN_TZ).date()
        failed, later = ((today - timedelta(days=offset)).isoformat() for offset in (2, 1))
        curve = {"points": [
            dict(t=f"{minute // 60:02d}:{minute % 60:02d}",
                 pv=900, load=900, batt=0, soc=100, grid=0)
            for minute in range(365, 1081, 5)
        ]}
        radiation = {
            f"{day}T{minute // 60:02d}:{minute % 60:02d}": 500
            for day in (failed, later)
            for minute in range(370, 1081, 10)
        }
        fetch = AsyncMock(side_effect=[RuntimeError("SEMS unavailable"), curve, curve])
        with TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.db", satellite_curtailment=True)
            store.backfill_daily({failed: 20, later: 20}, _today=today.isoformat())
            for offset in (4, 3):
                store.record_satellite_gain((today - timedelta(days=offset)).isoformat(), 10)
            runtime = SimpleNamespace(
                config={"capacity_kw": 16}, latest={"lat": 10, "lon": 106},
                history_provider=SimpleNamespace(fetch_day_curve=fetch), store=store,
            )
            with (patch.object(curtailment.satellite, "fetch_radiation", return_value=radiation),
                  patch.object(curtailment, "REQUEST_PAUSE_SECONDS", 0)):
                self.assertEqual(asyncio.run(curtailment.backfill_satellite(runtime)), 1)
                self.assertEqual(store.curtailment_days(), {later})
                self.assertEqual(asyncio.run(curtailment.backfill_satellite(runtime)), 1)
                self.assertEqual(store.curtailment_days(), {failed, later})
