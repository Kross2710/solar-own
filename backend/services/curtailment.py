"""Wasted solar (curtailment): the battery is full, so the inverter throttles PV down to the load."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, cast

from backend.runtime import AppRuntime
from providers.analytics import estimate_curtailment
from providers.base import Provider, VN_TZ
from providers.evn import EvnTariff
from providers.history import HistoryStore


# Rough monthly purchase when no history exists yet, to pick a marginal price.
DEFAULT_MONTHLY_BUY_KWH = 235
# Pause between day-curve requests to avoid the SEMS rate limit (GY0429).
REQUEST_PAUSE_SECONDS = 0.8
BACKFILL_DAYS = 30


def supports_day_curve(provider: Provider) -> bool:
    return callable(getattr(provider, "fetch_day_curve", None))


def marginal_price(store: HistoryStore, tariff: EvnTariff) -> int:
    """đ/kWh a wasted kWh would have avoided, at the tier currently being bought."""
    monthly_buy = sum((row.get("buy") or 0) for row in store.daily_full(35)[-30:])
    return round(tariff.marginal(monthly_buy or DEFAULT_MONTHLY_BUY_KWH))


async def curtail_for(provider: Provider, config: dict[str, Any], day: str) -> dict[str, Any]:
    fetch = cast(Callable[[str], Awaitable[dict[str, Any]]], getattr(provider, "fetch_day_curve"))
    points = (await fetch(day)).get("points") or []
    return estimate_curtailment(
        points,
        reserve_pct=float(config.get("battery_reserve_percent", 20)),
        capacity_kw=config.get("capacity_kw"),
    )


async def build_curtailment(runtime: AppRuntime) -> dict[str, Any]:
    """Wasted sun today (computed live) + the 30-day total (stored by the backfill)."""
    provider = runtime.history_provider
    if not supports_day_curve(provider):
        return {"supported": False}

    today = datetime.now(VN_TZ).date().isoformat()
    try:
        estimate = await curtail_for(provider, runtime.config, today)
    except Exception:
        estimate = {"lost_kwh": None, "full_at": None, "actual_kwh": None, "potential_kwh": None}

    by_day = {row["day"]: (row["lost"] or 0) for row in runtime.store.curtailment_recent(BACKFILL_DAYS)}
    if estimate.get("lost_kwh") is not None:
        by_day[today] = estimate["lost_kwh"]

    return {
        "supported": True,
        "currency": runtime.config.get("currency") or "VND",
        "marginal": marginal_price(runtime.store, runtime.tariff),
        "today": {
            "lost_kwh": estimate.get("lost_kwh"),
            "full_at": estimate.get("full_at"),
            "actual_kwh": estimate.get("actual_kwh"),
            "potential_kwh": estimate.get("potential_kwh"),
        },
        "total30_kwh": round(sum(value for value in by_day.values() if value), 1),
        "days": len(by_day),
        "recent": [
            {"day": day, "lost_kwh": round(by_day[day], 1)} for day in sorted(by_day)
        ],
    }


async def backfill_curtailment(
    store: HistoryStore,
    provider: Provider,
    config: dict[str, Any],
) -> int:
    """Fill missing days of the last 30 and refresh yesterday/today. Returns days written."""
    if not supports_day_curve(provider):
        return 0

    have = store.curtailment_days()
    yesterday = (datetime.now(VN_TZ).date() - timedelta(days=1)).isoformat()
    todo = [row["day"] for row in store.daily(BACKFILL_DAYS) if row["day"] not in have or row["day"] >= yesterday]

    written = 0
    for day in todo:
        try:
            estimate = await curtail_for(provider, config, day)
            store.record_curtailment(day, estimate.get("lost_kwh") or 0, estimate.get("full_at"))
            written += 1
        except Exception:
            pass
        await asyncio.sleep(REQUEST_PAUSE_SECONDS)
    return written
