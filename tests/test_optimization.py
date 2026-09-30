import asyncio
import math
from datetime import date, datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

from backend.services import curtailment as curtailment_service
from backend.services import forecast as forecast_service
from providers.base import VN_TZ
from providers.evn import EvnTariff
from providers.forecast import SolarForecaster


def _weather(day: str, rad: float) -> dict:
    return {
        "rad": rad, "sun": rad * 1500, "daylight": 43_000, "tmax": 33.0, "tmean": 29.0,
        "tmin": 25.0, "precip": 0.0 if rad > 15 else 6.0, "precip_h": 0.0 if rad > 15 else 5.0,
        "et0": rad / 4, "uv": None, "wcode": 1 if rad > 15 else 61, "rain_prob": None, "is_fcst": 0,
    }


class FakeStore:
    def __init__(self, days: int = 40) -> None:
        today = datetime.now(VN_TZ).date()
        self.rows = []
        self.weather: dict[str, dict] = {}
        for offset in range(days, 0, -1):
            day = (today - timedelta(days=offset)).isoformat()
            rad = 12 + 10 * (0.5 + 0.5 * math.sin(offset))
            self.rows.append({"day": day, "kwh": round(rad * 3.1, 1), "cons": 40.0, "buy": 10.0})
            self.weather[day] = _weather(day, rad)
        for offset in range(0, 6):
            day = (today + timedelta(days=offset)).isoformat()
            self.weather[day] = {**_weather(day, 20.0), "is_fcst": 1}
        self.curtailment: dict[str, tuple] = {}

    def daily_full(self, days: int = 400) -> list[dict]:
        return self.rows[-days:]

    def daily(self, days: int = 30) -> list[dict]:
        return self.rows[-days:]

    def weather_upsert(self, rows: dict) -> int:
        self.weather.update(rows)
        return len(rows)

    def weather_all(self) -> list[dict]:
        return [{"day": day, **value} for day, value in sorted(self.weather.items())]

    def training_rows(self) -> list[dict]:
        return [
            {**self.weather[row["day"]], "day": row["day"], "kwh": row["kwh"]}
            for row in self.rows
            if row["day"] in self.weather and not self.weather[row["day"]].get("is_fcst")
        ]

    def night_load_avg_kwh(self, days: int = 14) -> float:
        return 21.9

    def curtailment_days(self) -> set:
        return set(self.curtailment)

    def record_curtailment(self, day: str, lost: float, full_at) -> None:
        self.curtailment[day] = (lost, full_at)

    def curtailment_recent(self, days: int = 30) -> list[dict]:
        return [{"day": day, "lost": lost, "full_at": full_at} for day, (lost, full_at) in sorted(self.curtailment.items())]


class FakeRuntime:
    def __init__(self, store: FakeStore, provider=None) -> None:
        self.store = store
        self.tariff = EvnTariff()
        self.config = {"currency": "VND", "battery_reserve_percent": 20, "capacity_kw": 16}
        self.latest = {"lat": 10.8, "lon": 106.7}
        self.forecaster = SolarForecaster()
        self.forecast_lock = asyncio.Lock()
        self.history_provider = provider


async def _no_weather(*_args, **_kwargs) -> dict:
    return {}


class ForecastServiceTests(TestCase):
    def test_trains_and_serves_next_days(self) -> None:
        runtime = FakeRuntime(FakeStore())

        with patch.object(forecast_service.fc_mod, "fetch_archive_weather", _no_weather), \
                patch.object(forecast_service.fc_mod, "fetch_daily_weather", _no_weather):
            result = asyncio.run(forecast_service.build_forecast(runtime))  # type: ignore[arg-type]

        self.assertTrue(result["ready"])
        self.assertEqual(result["night_need_kwh"], 21.9)
        self.assertTrue(result["days"][0]["today"])
        self.assertEqual(len(result["days"]), 6)
        self.assertNotIn("board", result["quality"])
        self.assertIn(result["days"][1]["qual"], ("ít", "vừa", "tốt"))

    def test_not_ready_without_location(self) -> None:
        runtime = FakeRuntime(FakeStore())
        runtime.latest = {}

        result = asyncio.run(forecast_service.build_forecast(runtime))  # type: ignore[arg-type]

        self.assertEqual(result, {"ready": False, "reason": "not_enough_data"})


def _sunny_curve(full_from_minute: int) -> dict:
    points = []
    for minute in range(6 * 60, 18 * 60, 5):
        x = (minute - 6 * 60) / (12 * 60)
        potential = 12_000 * math.sin(math.pi * x)
        full = minute >= full_from_minute
        points.append({
            "t": f"{minute // 60:02d}:{minute % 60:02d}",
            "pv": min(potential, 3000) if full else potential,
            "soc": 100 if full else 60,
            "grid": 0,
        })
    return {"points": points}


class FakeCurveProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch_day_curve(self, day: str) -> dict:
        self.calls.append(day)
        return _sunny_curve(11 * 60)


class CurtailmentServiceTests(TestCase):
    def test_today_and_30_day_total(self) -> None:
        store = FakeStore()
        yesterday = store.rows[-1]["day"]
        store.record_curtailment(yesterday, 4.0, "11:00")
        runtime = FakeRuntime(store, FakeCurveProvider())

        result = asyncio.run(curtailment_service.build_curtailment(runtime))  # type: ignore[arg-type]

        self.assertTrue(result["supported"])
        self.assertGreater(result["today"]["lost_kwh"], 0)
        self.assertEqual(result["today"]["full_at"], "11:00")
        self.assertAlmostEqual(result["total30_kwh"], round(4.0 + result["today"]["lost_kwh"], 1))
        self.assertEqual([item["day"] for item in result["recent"]][0], yesterday)

    def test_unsupported_provider(self) -> None:
        runtime = FakeRuntime(FakeStore(), provider=object())

        result = asyncio.run(curtailment_service.build_curtailment(runtime))  # type: ignore[arg-type]

        self.assertEqual(result, {"supported": False})

    def test_backfill_fills_missing_days_and_refreshes_recent(self) -> None:
        store = FakeStore(days=5)
        known = store.rows[0]["day"]
        store.record_curtailment(known, 1.0, None)
        provider = FakeCurveProvider()

        with patch.object(curtailment_service, "REQUEST_PAUSE_SECONDS", 0):
            written = asyncio.run(curtailment_service.backfill_curtailment(store, provider, {}))  # type: ignore[arg-type]

        self.assertEqual(written, 4)
        self.assertNotIn(known, provider.calls)
        self.assertEqual(store.curtailment[known], (1.0, None))


class ArchiveEndTests(TestCase):
    def test_archive_end_is_clamped(self) -> None:
        from providers.forecast import archive_safe_end

        self.assertEqual(archive_safe_end("2026-09-30", today="2026-09-30"), "2026-09-25")
        self.assertEqual(archive_safe_end("2026-09-01", today="2026-09-30"), "2026-09-01")
        self.assertIsInstance(date.fromisoformat(archive_safe_end("2026-09-30")), date)
