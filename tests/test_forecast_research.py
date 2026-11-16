import math
from unittest import TestCase
from providers.analytics import estimate_curtailment
from tools.research.forecast_diagnostic import artificial_curtailment, valid_curve


class CurtailmentResearchTests(TestCase):
    def curve(self):
        return [{'t':f'{m//60:02d}:{m%60:02d}', 'pv':max(0,10000*math.sin(math.pi*(m-360)/720)), 'soc':70,'grid':0}
                for m in range(0,1440,5)]

    def test_potential_is_actual_plus_attributed_loss(self):
        points=self.curve()
        uncapped=estimate_curtailment(points)
        self.assertEqual(uncapped['lost_kwh'],0)
        self.assertEqual(uncapped['potential_kwh'],uncapped['actual_kwh'])
        capped=estimate_curtailment(artificial_curtailment(points,660))
        self.assertGreater(capped['lost_kwh'],0)
        self.assertAlmostEqual(capped['potential_kwh'],capped['actual_kwh']+capped['lost_kwh'])

    def test_hidden_peak_is_not_available_to_estimator(self):
        points=self.curve()
        simulated=artificial_curtailment(points,600)
        after=[p['pv'] for p in simulated if p['t'] >= '10:00']
        self.assertLessEqual(max(after),3000)
        self.assertEqual(max(p['soc'] for p in simulated),100)
        self.assertTrue(valid_curve(points)[1])
        missing=[p for p in points if not '10:00' <= p['t'] <= '11:00']
        self.assertFalse(valid_curve(missing)[1])
