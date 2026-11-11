from datetime import date
from unittest import TestCase
from backend.services.money import compute_money
from providers.evn import EvnTariff, DEFAULT_TIERS


class TariffDatesTests(TestCase):
    def test_change_date_and_marginal_boundaries(self):
        tariff = EvnTariff.from_config({'tiers': DEFAULT_TIERS})
        self.assertEqual(len(tariff.at('2026-10-31').tiers), 6)
        new = tariff.at('2026-11-01')
        self.assertEqual(len(new.tiers), 5)
        self.assertEqual(new.marginal(100, False), 2289)
        self.assertEqual(new.marginal(200, False), 2894)
        self.assertEqual(new.marginal(400, False), 3456)
        self.assertEqual(new.marginal(700, False), 3844)
        self.assertAlmostEqual(new.cost(800), (100*1901+100*2289+200*2894+300*3456+100*3844)*1.08)

    def test_mixed_cycle_does_not_grant_two_full_tier_quotas(self):
        tariff = EvnTariff()
        start, end = date(2026, 10, 16), date(2026, 11, 16)
        expected = (tariff.at(start).cost(500)*16 + tariff.at('2026-11-01').cost(500)*15)/31
        self.assertAlmostEqual(tariff.period_cost(500, start, end), expected)
        self.assertTrue(tariff.period_info(start, end)['mixed'])
        self.assertEqual(tariff.period_info(start, end)['allocation'], 'estimated_by_days')

    def test_all_time_savings_preserve_old_month_and_use_new_month(self):
        tariff = EvnTariff()
        rows = [{'day':'2026-10-01','cons':1000,'buy':300}, {'day':'2026-11-01','cons':1000,'buy':300}]
        money = compute_money(rows, tariff, 1, date(2026,11,1))
        expected = tariff.at('2026-10-01').savings(1000,300) + tariff.at('2026-11-01').savings(1000,300)
        self.assertEqual(money['total']['saved'],round(expected))
        self.assertEqual(money['tier']['count'],5)
        self.assertEqual(money['prev_cycle']['bill'],round(tariff.at('2026-10-01').cost(300)))

    def test_custom_tariff_is_not_replaced_by_evn(self):
        tariff = EvnTariff.from_config({'tiers':[(None,1234)],'vat':0})
        self.assertEqual(tariff.at('2026-11-01').cost(100),123400)
        with self.assertRaises(ValueError):
            EvnTariff([(100,1000),(50,2000),(None,3000)])
