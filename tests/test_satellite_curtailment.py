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
