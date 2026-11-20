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
