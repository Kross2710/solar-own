from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.runtime import AppRuntime
from providers.base import Metrics, Provider
from providers.evn import EvnTariff


class FakeProvider(Provider):
    name = "mock"

    async def get_metrics(self) -> Metrics:
        return Metrics(
            source="mock",
            status="online",
            pv_power_w=1200,
            load_power_w=800,
            battery_soc=75,
        )


class FakeStore:
    rows = [
        {
            "day": "2026-09-01",
            "kwh": 20.0,
            "cons": 16.0,
            "buy": 1.0,
            "batt": 2.0,
        }
    ]

    def record(self, metrics: dict) -> None:
        return None

    def meter_today(self, day: str, buy: float, sell: float) -> tuple:
        return buy, sell

    def recent(self, hours: int) -> list[dict]:
        return [{"ts": "2026-09-01T12:00:00", "pv": 1200, "soc": 75}]

    def daily_full(self, days: int) -> list[dict]:
        return self.rows[-days:]

    def hourly_profile(self, days: int) -> list[dict]:
        return [{"hour": h, "pv": 0, "load": 500, "grid": 500, "n": 1} for h in range(24)]

    def monthly(self, months: int) -> list[dict]:
        return [
            {
                "month": "2026-09",
                "kwh": 20.0,
                "cons": 16.0,
                "buy": 1.0,
                "days": 1,
                "cons_days": 1,
                "buy_days": 1,
                "batt": 2.0,
                "batt_days": 1,
            }
        ]

    def yearly(self) -> list[dict]:
        return [
            {
                "year": "2026",
                "kwh": 20.0,
                "cons": 16.0,
                "buy": 1.0,
                "days": 1,
            }
        ]


class ApiSmokeTests(TestCase):
    def setUp(self) -> None:
        provider = FakeProvider()
        runtime = AppRuntime(
            root=Path("."),
            config={"source": "mock", "currency": "VND"},
            live_provider=provider,
            history_provider=provider,
            poll_interval=5,
            store=FakeStore(),  # type: ignore[arg-type]
            tariff=EvnTariff(),
        )
        self.client_context = TestClient(
            create_app(runtime, mount_static=False)
        )
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_metrics_route(self) -> None:
        response = self.client.get("/api/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pv_power_w"], 1200)

    def test_history_routes(self) -> None:
        self.assertEqual(self.client.get("/api/history?hours=24").status_code, 200)
        self.assertEqual(self.client.get("/api/daily?days=30").status_code, 200)

        day = self.client.get("/api/day?date=2026-09-01").json()
        self.assertEqual(day["error"], "not_supported")

        summary = self.client.get("/api/summary").json()
        self.assertEqual(summary["currency"], "VND")
        self.assertEqual(summary["monthly"][0]["kwh"], 20.0)

        money = self.client.get("/api/money")
        self.assertEqual(money.status_code, 200)
        self.assertEqual(money.json()["currency"], "VND")
        self.assertIsNone(money.json()["payback"])
        self.assertNotIn("evn_bill", money.json())
        self.assertEqual(money.json()["evn_history"], [])
        self.assertEqual(money.json()["solar_start"], "2026-09-01")

        self.assertEqual(self.client.get("/api/curtailment").json(), {"supported": False})
        self.assertEqual(self.client.get("/api/forecast").json()["ready"], False)

    def test_hourly_route(self) -> None:
        hourly = self.client.get("/api/hourly").json()

        self.assertEqual(hourly["currency"], "VND")
        self.assertEqual(len(hourly["hours"]), 24)
        self.assertGreater(hourly["marginal"], 0)
