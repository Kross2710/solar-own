"""Proactive notices: deterministic rules (no LLM, so nothing is made up).

Only unusual events are reported. Things that happen every day (the battery filling up
around 11:00 and wasting sun) live on their own card instead of repeating as notices.
Each notice expires after NOTICE_TTL; the UI builds the sentence from kind + data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from backend.runtime import AppRuntime
from backend.services.curtailment import marginal_price
from backend.services.money import build_money, tier_ladder
from providers.base import VN_TZ


CHECK_INTERVAL_SECONDS = 15 * 60
WAIT_FOR_SYNC_SECONDS = 10 * 60
NOTICE_TTL = timedelta(days=2)
OFFLINE_TTL = timedelta(days=1)

OFFLINE_MINUTES = 30
# Last night used this much more than the 14-night average, and by at least NIGHT_MIN_DELTA_KWH.
NIGHT_RATIO = 1.5
NIGHT_MIN_DELTA_KWH = 1.0
# The flat projection swings a lot in the first days of a cycle.
BILL_MIN_DAYS = 7
BILL_RATIO = 1.2
BILL_MIN_DELTA_VND = 50_000
TIER_MIN_DAYS = 5
# Zero-based tier index from which a higher price is worth a heads-up (tier 4 and up).
TIER_WARN_INDEX = 3
# This week's wasted sun must clearly exceed last week's to be news.
CURTAIL_RATIO = 1.5
CURTAIL_MIN_DELTA_KWH = 15.0
CURTAIL_MIN_DAYS = 12

OFFLINE = "offline"


@dataclass
class OfflineWatch:
    since: datetime | None = None


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M")


def check_offline(runtime: AppRuntime, watch: OfflineWatch, now: datetime) -> int:
    store = runtime.store
    latest = runtime.latest or {}
    if latest.get("status") != "offline":
        watch.since = None
        # Back online: the offline notice is no longer true.
        for notice in store.notices_recent(10, active_at=_stamp(now)):
            if notice["kind"] == OFFLINE:
                store.notice_dismiss(notice["id"])
        return 0

    watch.since = watch.since or now
    minutes = (now - watch.since).total_seconds() / 60
    if minutes < OFFLINE_MINUTES:
        return 0
    return int(store.notice_add(
        OFFLINE, _stamp(watch.since), "warn", {"since": _stamp(watch.since)}, _stamp(now + OFFLINE_TTL)
    ))


def check_night_load(runtime: AppRuntime, now: datetime) -> int:
    store = runtime.store
    yesterday = (now.date() - timedelta(days=1)).isoformat()
    night = store.night_load_kwh(yesterday)
    average = store.night_load_avg_kwh(14)
    if night is None or not average:
        return 0
    if night <= average * NIGHT_RATIO or night - average <= NIGHT_MIN_DELTA_KWH:
        return 0
    return int(store.notice_add(
        "night_load_high", yesterday, "warn",
        {"night": yesterday, "night_kwh": round(night, 1), "avg_kwh": round(average, 1)},
        _stamp(now + NOTICE_TTL),
    ))


def check_money(runtime: AppRuntime, now: datetime) -> int:
    """Projected bill well above the last real bill; an expensive tier coming this cycle."""
    money = build_money(runtime, now.date())
    cycle = money["cycle"]
    tier = money["tier"]
    elapsed = cycle["days_elapsed"]
    expires = _stamp(now + NOTICE_TTL)
    added = 0

    last_bill = (money.get("evn_bill") or {}).get("amount")
    projected = cycle["bill_proj"]
    if (
        elapsed >= BILL_MIN_DAYS
        and last_bill
        and projected > last_bill * BILL_RATIO
        and projected - last_bill > BILL_MIN_DELTA_VND
    ):
        added += runtime.store.notice_add(
            "bill_high", cycle["start"], "warn",
            {"proj": projected, "last": last_bill, "last_cycle": money["evn_bill"]["cycle"],
             "pct": round((projected - last_bill) / last_bill * 100)},
            expires,
        )

    next_index = tier["index"] + 1
    to_next = tier["to_next_kwh"]
    if elapsed >= TIER_MIN_DAYS and to_next is not None and next_index >= TIER_WARN_INDEX:
        projected_tier = tier_ladder(runtime.tariff, cycle["proj_buy_kwh"])
        if projected_tier["index"] >= next_index:
            per_day = cycle["buy_kwh"] / elapsed
            days_left = round(to_next / per_day) if per_day > 0 else None
            added += runtime.store.notice_add(
                "tier_ahead", f"{cycle['start']}#{next_index}", "info",
                {"tier": next_index + 1, "price": tier["prices"][next_index], "cur_price": tier["cur_price"],
                 "to_next_kwh": to_next, "days_left": days_left},
                expires,
            )
    return added


def check_curtailment(runtime: AppRuntime, now: datetime) -> int:
    rows = runtime.store.curtailment_recent(15)
    yesterday = (now.date() - timedelta(days=1)).isoformat()
    rows = [row for row in rows if row["day"] <= yesterday][-14:]
    if len(rows) < CURTAIL_MIN_DAYS:
        return 0
    this_week, last_week = rows[-7:], rows[:-7]
    lost = sum(row.get("lost") or 0 for row in this_week)
    before = sum(row.get("lost") or 0 for row in last_week) * 7 / max(1, len(last_week))
    if lost < before * CURTAIL_RATIO or lost - before < CURTAIL_MIN_DELTA_KWH:
        return 0

    full_times = sorted(row["full_at"] for row in this_week if row.get("full_at"))
    year, week, _ = date.fromisoformat(yesterday).isocalendar()
    return int(runtime.store.notice_add(
        "wasted_sun_up", f"{year}-W{week:02d}", "info",
        {"lost_kwh": round(lost, 1), "prev_kwh": round(before, 1),
         "value": round(lost * marginal_price(runtime.store, runtime.tariff)),
         "full_at": full_times[len(full_times) // 2] if full_times else None},
        _stamp(now + NOTICE_TTL),
    ))


def check_notices(runtime: AppRuntime, watch: OfflineWatch, now: datetime | None = None) -> int:
    now = now or datetime.now(VN_TZ)
    added = 0
    for rule in (
        lambda: check_offline(runtime, watch, now),
        lambda: check_night_load(runtime, now),
        lambda: check_money(runtime, now),
        lambda: check_curtailment(runtime, now),
    ):
        try:
            added += rule()
        except Exception as error:
            print(f"  [notices] rule error: {type(error).__name__}: {error}", flush=True)
    return added


def active_notices(runtime: AppRuntime, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(VN_TZ)
    notices = runtime.store.notices_recent(10, active_at=_stamp(now))
    severity_rank = {"warn": 0, "info": 1}
    notices.sort(key=lambda notice: (severity_rank.get(notice["severity"], 2), -notice["id"]))
    return notices


async def notices_loop(runtime: AppRuntime) -> None:
    try:
        await asyncio.wait_for(runtime.synced.wait(), timeout=WAIT_FOR_SYNC_SECONDS)
    except asyncio.TimeoutError:
        pass
    watch = OfflineWatch()
    while True:
        try:
            added = check_notices(runtime, watch)
            if added:
                print(f"  [notices] {added} new", flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"  [notices] error: {type(error).__name__}: {error}", flush=True)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
