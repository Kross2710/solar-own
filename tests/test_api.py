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
        self.assertIsNone(hourly["marginal"])  # no purchase data in the current cycle


class ThrowingProvider(Provider):
    """Provider whose day-curve fetch always fails — exercises the error path."""

    name = "throwing"

    async def get_metrics(self) -> Metrics:
        return Metrics(
            source="throwing",
            status="online",
            pv_power_w=1,
            load_power_w=1,
            battery_soc=50,
        )

    async def fetch_day_curve(self, day: str) -> dict:
        raise ValueError(f"boom from {day}")


class FailingMetricsProvider(Provider):
    """Provider whose get_metrics always fails — exercises /api/metrics error path."""

    name = "failing"

    async def get_metrics(self) -> Metrics:
        raise RuntimeError("metrics backend down")


class ApiParameterValidationTests(TestCase):
    """Issue #32: /api params must be validated, not echoed or silently clamped."""

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

    # --- /api/day date validation ---

    def test_valid_date_ok(self) -> None:
        resp = self.client.get("/api/day?date=2026-09-01")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["error"], "not_supported")

    def test_garbage_date_is_422(self) -> None:
        resp = self.client.get("/api/day?date=notadate")
        self.assertEqual(resp.status_code, 422)
        # No Python exception name or message leaked into the public payload.
        self.assertNotIn("ValueError", resp.text)
        self.assertNotIn("isoformat", resp.text)

    def test_bad_calendar_date_is_422(self) -> None:
        # 2026-02-30 is well-formed but not a real calendar date.
        resp = self.client.get("/api/day?date=2026-02-30")
        self.assertEqual(resp.status_code, 422)
        self.assertNotIn("ValueError", resp.text)
        self.assertNotIn("day is out of range", resp.text)

    # --- /api/history hours bounds ---

    def test_hours_zero_is_422(self) -> None:
        self.assertEqual(self.client.get("/api/history?hours=0").status_code, 422)

    def test_hours_negative_is_422(self) -> None:
        self.assertEqual(self.client.get("/api/history?hours=-5").status_code, 422)

    def test_hours_over_limit_is_422(self) -> None:
        self.assertEqual(self.client.get("/api/history?hours=99999").status_code, 422)

    def test_hours_within_bounds_ok(self) -> None:
        self.assertEqual(self.client.get("/api/history?hours=1").status_code, 200)
        self.assertEqual(self.client.get("/api/history?hours=24").status_code, 200)
        self.assertEqual(self.client.get("/api/history?hours=1000").status_code, 200)

    # --- /api/daily days bounds ---

    def test_days_zero_is_422(self) -> None:
        self.assertEqual(self.client.get("/api/daily?days=0").status_code, 422)

    def test_days_over_limit_is_422(self) -> None:
        self.assertEqual(self.client.get("/api/daily?days=99999").status_code, 422)

    def test_days_within_bounds_ok(self) -> None:
        self.assertEqual(self.client.get("/api/daily?days=1").status_code, 200)
        self.assertEqual(self.client.get("/api/daily?days=30").status_code, 200)
        self.assertEqual(self.client.get("/api/daily?days=1000").status_code, 200)


class ApiDayErrorHandlingTests(TestCase):
    """Issue #32: a genuine provider failure returns a generic code, not an echo."""

    def setUp(self) -> None:
        provider = ThrowingProvider()
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

    def test_provider_failure_returns_generic_error(self) -> None:
        resp = self.client.get("/api/day?date=2026-09-01")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["error"], "fetch_failed")
        # The caller's input and the internal exception must not leak out.
        self.assertNotIn("ValueError", resp.text)
        self.assertNotIn("boom", resp.text)
        self.assertEqual(body["date"], "2026-09-01")
        self.assertEqual(body["points"], [])


class ApiMetricsErrorHandlingTests(TestCase):
    """Issue #32 (related): /api/metrics must not echo the internal exception."""

    def setUp(self) -> None:
        provider = FailingMetricsProvider()
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

    def test_metrics_failure_returns_generic_error(self) -> None:
        resp = self.client.get("/api/metrics")
        body = resp.json()
        self.assertEqual(body["error"], "snapshot_failed")
        self.assertNotIn("RuntimeError", resp.text)
        self.assertNotIn("metrics backend down", resp.text)
