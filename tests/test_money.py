from datetime import date
from unittest import TestCase

from backend.services.money import (
    compute_money,
    cycle_bounds,
    evn_bill_block,
    evn_bill_history,
    tier_ladder,
)
from providers.evn import EvnTariff


class CycleBoundsTests(TestCase):
    def test_start_day_one(self) -> None:
        self.assertEqual(
            cycle_bounds(date(2026, 9, 30), 1),
            (date(2026, 9, 1), 30, 30, date(2026, 10, 1)),
        )

    def test_before_start_day_uses_previous_month(self) -> None:
        start, days_in_cycle, days_elapsed, end = cycle_bounds(date(2026, 9, 10), 15)
        self.assertEqual((start, end), (date(2026, 8, 15), date(2026, 9, 15)))
        self.assertEqual((days_in_cycle, days_elapsed), (31, 27))

    def test_start_day_clamped_in_short_month(self) -> None:
        start, _, _, end = cycle_bounds(date(2026, 2, 28), 31)
        self.assertEqual((start, end), (date(2026, 2, 28), date(2026, 3, 31)))


class TierLadderTests(TestCase):
    def test_middle_tier(self) -> None:
        tier = tier_ladder(EvnTariff(), 120)
        self.assertEqual(tier["index"], 2)
        self.assertEqual(tier["to_next_kwh"], 80.0)
        self.assertGreater(tier["next_jump"], 0)

    def test_top_tier_has_no_next(self) -> None:
        tier = tier_ladder(EvnTariff(), 1000)
        self.assertEqual(tier["index"], tier["count"] - 1)
        self.assertIsNone(tier["to_next_kwh"])
        self.assertIsNone(tier["next_jump"])


class ComputeMoneyTests(TestCase):
    def setUp(self) -> None:
        self.tariff = EvnTariff()
        self.rows = [
            {"day": "2026-08-01", "cons": 40.0, "buy": 10.0},
            {"day": "2026-08-02", "cons": 40.0, "buy": 10.0},
            {"day": "2026-09-01", "cons": 40.0, "buy": 8.0},
            {"day": "2026-09-02", "cons": 30.0, "buy": 6.0},
        ]

    def test_cycle_and_today(self) -> None:
        money = compute_money(self.rows, self.tariff, 1, date(2026, 9, 2))
        cycle = money["cycle"]

        self.assertEqual(cycle["buy_kwh"], 14.0)
        self.assertEqual(cycle["cons_kwh"], 70.0)
        self.assertEqual(cycle["bill_now"], round(self.tariff.cost(14.0)))
        self.assertEqual(
            cycle["saved_now"],
            round(self.tariff.cost(70.0) - self.tariff.cost(14.0)),
        )
        self.assertEqual(cycle["proj_method"], "flat")
        self.assertEqual(cycle["proj_buy_kwh"], 210)
        self.assertEqual(money["today"]["selfuse_kwh"], 24.0)
        self.assertEqual(money["total"]["months"], 2)
        self.assertIsNone(money["payback"])

    def test_previous_cycle_compares_same_elapsed_days(self) -> None:
        prev = compute_money(self.rows, self.tariff, 1, date(2026, 9, 2))["prev_cycle"]

        self.assertEqual(prev["start"], "2026-08-01")
        self.assertEqual(prev["days"], 2)
        self.assertEqual(prev["buy_kwh"], 20.0)
        self.assertEqual(prev["buy_delta_pct"], -30)
        self.assertLess(prev["bill_delta"], 0)

    def test_payback(self) -> None:
        money = compute_money(
            self.rows, self.tariff, 1, date(2026, 9, 2), invest_total=100_000_000
        )
        payback = money["payback"]

        self.assertEqual(payback["recovered"], money["total"]["saved"])
        self.assertEqual(payback["data_months"], 2)
        self.assertTrue(payback["low_confidence"])
        self.assertFalse(payback["done"])


class EvnBillBlockTests(TestCase):
    def test_uses_latest_closed_cycle(self) -> None:
        rows = [{"day": f"2026-08-{d:02d}", "buy": 10.0} for d in range(1, 32)]
        bills = [
            {"cycle": "2026-07", "kwh": 290, "amount": 800_000, "paid_date": "2026-08-03"},
            {"cycle": "2026-08", "kwh": 310, "amount": 850_000, "paid_date": "2026-09-03"},
            {"cycle": "2026-09", "kwh": None, "amount": 900_000, "paid_date": None},
        ]
        block = evn_bill_block(bills, rows, EvnTariff(), date(2026, 9, 30))

        assert block is not None
        self.assertEqual(block["cycle"], "2026-08")
        self.assertTrue(block["est_reliable"])
        self.assertIsNotNone(block["diff_pct"])

    def test_unreliable_when_first_day_missing(self) -> None:
        rows = [{"day": f"2026-08-{d:02d}", "buy": 10.0} for d in range(2, 32)]
        bills = [{"cycle": "2026-08", "kwh": 310, "amount": 850_000, "paid_date": None}]
        block = evn_bill_block(bills, rows, EvnTariff(), date(2026, 9, 30))

        assert block is not None
        self.assertFalse(block["est_reliable"])
        self.assertIsNone(block["diff_pct"])

    def test_none_without_closed_bill(self) -> None:
        self.assertIsNone(evn_bill_block([], [], EvnTariff(), date(2026, 9, 30)))


class EvnBillHistoryTests(TestCase):
    def test_keeps_latest_closed_cycles_oldest_first(self) -> None:
        bills = [
            {"cycle": f"2025-{m:02d}", "amount": 1_000_000 + m} for m in range(1, 13)
        ] + [
            {"cycle": "2026-01", "amount": None},
            {"cycle": "2026-02", "amount": 500_000.4},
            {"cycle": "2026-03", "amount": 600_000},
        ]
        history = evn_bill_history(bills, date(2026, 3, 15), limit=4)

        self.assertEqual(
            history,
            [
                {"cycle": "2025-10", "amount": 1_000_010},
                {"cycle": "2025-11", "amount": 1_000_011},
                {"cycle": "2025-12", "amount": 1_000_012},
                {"cycle": "2026-02", "amount": 500_000},
            ],
        )
