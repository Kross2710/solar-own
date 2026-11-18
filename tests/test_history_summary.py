from unittest import TestCase

from backend.services.history_summary import compute_records, compute_stats


class HistorySummaryTests(TestCase):
    def setUp(self) -> None:
        self.rows = [
            {"day": "2026-08-30", "kwh": 10.0, "cons": 12.0, "buy": 4.0},
            {"day": "2026-08-31", "kwh": 14.0, "cons": 14.0, "buy": 2.0},
            {"day": "2026-09-01", "kwh": 20.0, "cons": 16.0, "buy": 1.0},
        ]

    def test_compute_records(self) -> None:
        records = compute_records(self.rows)

        self.assertEqual(
            records["best_day"],
            {"day": "2026-09-01", "kwh": 20.0},
        )
        self.assertEqual(records["best_self_day"]["pct"], 94)
        self.assertEqual(records["peak_month"]["month"], "2026-08")
        self.assertEqual(records["streak"]["days"], 3)

    def test_compute_stats(self) -> None:
        stats = compute_stats(self.rows, price=2500, currency="VND")

        self.assertEqual(stats["total_kwh"], 44.0)
        self.assertEqual(stats["total_savings"], 110_000)
        self.assertEqual(stats["best_day"]["day"], "2026-09-01")
        self.assertEqual(stats["currency"], "VND")
