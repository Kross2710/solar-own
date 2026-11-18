import asyncio
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from unittest import TestCase
from unittest.mock import patch

from backend.runtime import AppRuntime
from backend.services import curtailment as curtailment_service
from backend.services import notices as notices_service
from backend.services import sync as sync_service
from providers.base import Metrics, Provider, VN_TZ
from providers.evn import EvnTariff
from providers.history import HistoryStore


class FakeSems(Provider):
    name = "sems"

    def __init__(self, days: int = 20) -> None:
        today = datetime.now(VN_TZ).date()
        self.days = [(today - timedelta(days=n)).isoformat() for n in range(days, 0, -1)]
        self.months_asked: list[int] = []
        self.curves: list[str] = []

    async def get_metrics(self) -> Metrics:
        return Metrics(source="cloud", status="online")

    async def fetch_daily_history(self, months: int = 18) -> dict:
        self.months_asked.append(months)
        return {day: 30.0 for day in self.days}

    async def fetch_daily_energy(self, months: int = 18) -> dict:
        return {day: {"cons": 40.0, "buy": 8.0} for day in self.days}

    async def fetch_day_curve(self, day: str) -> dict:
        self.curves.append(day)
        return {"points": [{"t": "12:00", "pv": 3000, "load": 1000, "soc": 60}]}


class NightStore(HistoryStore):
    """Real store with the sample-based night estimates pinned."""

    night: Optional[float] = None
    night_avg: Optional[float] = None

    def night_load_kwh(self, day: str) -> Optional[float]:
        return self.night

    def night_load_avg_kwh(self, days: int = 14) -> Optional[float]:
        return self.night_avg


def _runtime(store: HistoryStore, provider: Provider, config: Optional[dict] = None) -> AppRuntime:
    return AppRuntime(
        root=Path("."),
        config=config or {"source": "cloud", "currency": "VND"},
        live_provider=provider,
        history_provider=provider,
        poll_interval=5,
        store=store,
        tariff=EvnTariff(),
    )


class TempStoreCase(TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = NightStore(Path(self.tmp.name) / "history.db")

    def tearDown(self) -> None:
        self.tmp.cleanup()


class SyncWindowTests(TestCase):
    today = date(2026, 9, 30)

    def _rows(self, days: list[str]) -> list[dict]:
        return [{"day": day, "kwh": 30.0, "cons": 40.0} for day in days]

    def test_empty_history_reads_everything(self) -> None:
        self.assertEqual(sync_service.sync_window_months([], self.today, 18), 18)

    def test_complete_history_reads_only_recent_months(self) -> None:
        days = [(self.today - timedelta(days=n)).isoformat() for n in range(200, 0, -1)]
        self.assertEqual(sync_service.sync_window_months(self._rows(days), self.today, 18), 2)

    def test_reads_back_to_the_oldest_hole(self) -> None:
        days = [(self.today - timedelta(days=n)).isoformat() for n in range(200, 0, -1) if n != 100]
        self.assertEqual(sync_service.sync_window_months(self._rows(days), self.today, 18), 5)

    def test_missing_usage_counts_as_a_hole(self) -> None:
        days = [(self.today - timedelta(days=n)).isoformat() for n in range(60, 0, -1)]
        rows = self._rows(days)
        rows[5]["cons"] = None
        self.assertEqual(sync_service.sync_window_months(rows, self.today, 18), 3)


class SyncOnceTests(TempStoreCase):
    def setUp(self) -> None:
        super().setUp()
        pauses = [
            patch.object(sync_service, "REQUEST_PAUSE_SECONDS", 0),
            patch.object(curtailment_service, "REQUEST_PAUSE_SECONDS", 0),
        ]
        for pause in pauses:
            pause.start()
            self.addCleanup(pause.stop)

    def test_first_sync_fills_daily_samples_and_curtailment(self) -> None:
        provider = FakeSems(days=20)
        runtime = _runtime(self.store, provider)

        asyncio.run(sync_service.sync_once(runtime))

        self.assertEqual(provider.months_asked, [18])
        self.assertEqual(self.store.daily_count(), 20)
        self.assertEqual(len(self.store.curtailment_days()), 20)
        self.assertEqual(len(provider.curves), 2 + 20)

        asyncio.run(sync_service.sync_once(runtime))
        self.assertEqual(provider.months_asked, [18, 2])

    def test_evn_backfills_once_then_syncs_recent_window(self) -> None:
        calls: list[tuple] = []

        class Portal:
            async def backfill(self, store) -> dict:
                calls.append(("backfill",))
                store.evn_backfill_daily({"2026-09-01": {"kwh": 8.0}})
                return {"days": 1, "bills": 0}

            async def sync_recent(self, store, days: int = 45) -> dict:
                calls.append(("recent", days))
                return {"days": days, "bills": 0}

        runtime = _runtime(self.store, FakeSems())
        asyncio.run(sync_service.evn_sync_once(runtime, Portal()))
        asyncio.run(sync_service.evn_sync_once(runtime, Portal()))

        self.assertEqual(calls[0], ("backfill",))
        self.assertEqual(calls[1][0], "recent")
        gap = (datetime.now(VN_TZ).date() - date(2026, 9, 1)).days
        self.assertEqual(calls[1][1], max(sync_service.EVN_RECENT_DAYS, gap + 7))


class NoticeTests(TempStoreCase):
    now = datetime(2026, 9, 20, 12, 0, tzinfo=VN_TZ)

    def _runtime(self, status: str = "online") -> AppRuntime:
        runtime = _runtime(self.store, FakeSems(), {"source": "cloud", "currency": "VND", "evn": {"cycle_start_day": 1}})
        runtime.latest = {"status": status}
        return runtime

    def _kinds(self, now: Optional[datetime] = None) -> list[str]:
        moment = now or self.now
        return [notice["kind"] for notice in self.store.notices_recent(20, active_at=moment.strftime("%Y-%m-%dT%H:%M"))]

    def test_unusual_night_fires_once(self) -> None:
        self.store.night, self.store.night_avg = 40.0, 24.0
        runtime = self._runtime()

        self.assertEqual(notices_service.check_night_load(runtime, self.now), 1)
        self.assertEqual(notices_service.check_night_load(runtime, self.now), 0)
        self.assertEqual(self._kinds(), ["night_load_high"])

    def test_normal_night_is_quiet(self) -> None:
        self.store.night, self.store.night_avg = 26.0, 24.0
        self.assertEqual(notices_service.check_night_load(self._runtime(), self.now), 0)

    def test_notices_expire(self) -> None:
        self.store.night, self.store.night_avg = 40.0, 24.0
        notices_service.check_night_load(self._runtime(), self.now)

        self.assertEqual(self._kinds(self.now + timedelta(days=3)), [])

    def test_offline_fires_after_threshold_and_clears_when_back(self) -> None:
        runtime = self._runtime(status="offline")
        watch = notices_service.OfflineWatch()

        self.assertEqual(notices_service.check_offline(runtime, watch, self.now), 0)
        later = self.now + timedelta(minutes=notices_service.OFFLINE_MINUTES + 1)
        self.assertEqual(notices_service.check_offline(runtime, watch, later), 1)
        self.assertEqual(self._kinds(later), ["offline"])

        runtime.latest = {"status": "online"}
        notices_service.check_offline(runtime, watch, later)
        self.assertEqual(self._kinds(later), [])

    def _curtailment(self, before: float, this_week: float) -> None:
        yesterday = self.now.date() - timedelta(days=1)
        for n in range(14):
            day = (yesterday - timedelta(days=n)).isoformat()
            self.store.record_curtailment(day, this_week if n < 7 else before, "10:30")

    def test_daily_wasted_sun_is_not_news(self) -> None:
        self._curtailment(before=20.0, this_week=20.0)
        self.assertEqual(notices_service.check_curtailment(self._runtime(), self.now), 0)

    def test_wasted_sun_jump_fires_once_per_week(self) -> None:
        self._curtailment(before=2.0, this_week=8.0)
        runtime = self._runtime()

        self.assertEqual(notices_service.check_curtailment(runtime, self.now), 1)
        self.assertEqual(notices_service.check_curtailment(runtime, self.now + timedelta(hours=6)), 0)
        notice = self.store.notices_recent(1)[0]
        self.assertEqual(notice["data"]["lost_kwh"], 56.0)
        self.assertEqual(notice["data"]["full_at"], "10:30")

    def _cycle_usage(self, buy_per_day: float, days: int) -> None:
        start = self.now.date().replace(day=1)
        rows = {(start + timedelta(days=n)).isoformat(): {"cons": buy_per_day + 20, "buy": buy_per_day} for n in range(days)}
        self.store.backfill_energy(rows)

    def test_expensive_tier_ahead_and_high_bill(self) -> None:
        self._cycle_usage(buy_per_day=12.0, days=19)
        self.store.evn_backfill_bills({"2026-08": {"kwh": 180.0, "amount": 500_000, "paid_date": "2026-09-05"}})
        runtime = self._runtime()

        self.assertEqual(notices_service.check_money(runtime, self.now), 2)
        by_kind = {notice["kind"]: notice for notice in self.store.notices_recent(5)}
        self.assertEqual(by_kind["tier_ahead"]["data"]["tier"], 5)
        self.assertEqual(by_kind["tier_ahead"]["data"]["days_left"], 6)
        self.assertEqual(by_kind["bill_high"]["data"]["last"], 500_000)
        self.assertEqual(notices_service.check_money(runtime, self.now), 0)

    def test_early_cycle_is_quiet(self) -> None:
        early = datetime(2026, 9, 3, 12, 0, tzinfo=VN_TZ)
        start = early.date().replace(day=1)
        self.store.backfill_energy({(start + timedelta(days=n)).isoformat(): {"cons": 90.0, "buy": 70.0} for n in range(3)})
        self.store.evn_backfill_bills({"2026-08": {"kwh": 180.0, "amount": 500_000, "paid_date": "2026-09-05"}})

        self.assertEqual(notices_service.check_money(self._runtime(), early), 0)

    def test_warnings_sort_first(self) -> None:
        expires = (self.now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        self.store.notice_add("wasted_sun_up", "w1", "info", {}, expires)
        self.store.notice_add("night_load_high", "n1", "warn", {}, expires)
        self.store.notice_add("tier_ahead", "t1", "info", {}, expires)

        kinds = [n["kind"] for n in notices_service.active_notices(self._runtime(), self.now)]
        self.assertEqual(kinds, ["night_load_high", "tier_ahead", "wasted_sun_up"])
