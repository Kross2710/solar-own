"""Wasted solar (curtailment): the battery is full, so the inverter throttles PV down to the load."""

from __future__ import annotations

import asyncio
from statistics import median
from time import monotonic
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, cast

from backend.runtime import AppRuntime
from providers.analytics import estimate_curtailment
from providers import satellite_curtailment as satellite
from providers.base import Provider, VN_TZ
from providers.evn import EvnTariff
from providers.history import HistoryStore
from backend.services.money import cycle_bounds


# Pause between day-curve requests to avoid the SEMS rate limit (GY0429).
REQUEST_PAUSE_SECONDS = 0.8
BACKFILL_DAYS = 30


def supports_day_curve(provider: Provider) -> bool:
    return callable(getattr(provider, "fetch_day_curve", None))


def projected_grid_use(store: HistoryStore, today: date, start_day: int = 1) -> tuple[float | None, date, date]:
    start, days, elapsed, end = cycle_bounds(today, start_day)
    rows = [row for row in store.daily_full(70) if start.isoformat() <= row["day"] <= today.isoformat()
            and row.get("buy") is not None]
    # Never fabricate a default price when there is no purchase history.
    if not rows:
        return None, start, end
    return sum(row["buy"] for row in rows) * days / elapsed, start, end


def marginal_price(store: HistoryStore, tariff: EvnTariff, start_day: int = 1, today: date | None = None) -> int | None:
    """Price of the next kWh at estimated end-of-cycle use, VAT included."""
    today = today or datetime.now(VN_TZ).date()
    projected, _, end = projected_grid_use(store, today, start_day)
    return None if projected is None else round(tariff.at(end - timedelta(days=1)).marginal(projected))


def grid_reduction_value(store: HistoryStore, tariff: EvnTariff, kwh: float, start_day: int = 1,
                         today: date | None = None) -> int | None:
    today = today or datetime.now(VN_TZ).date()
    projected, start, end = projected_grid_use(store, today, start_day)
    if projected is None:
        return None
    return round(tariff.period_cost(projected, start, end)
                 - tariff.period_cost(max(0, projected - max(0, kwh)), start, end))


async def curtail_for(provider: Provider, config: dict[str, Any], day: str) -> dict[str, Any]:
    fetch = cast(Callable[[str], Awaitable[dict[str, Any]]], getattr(provider, "fetch_day_curve"))
    points = (await fetch(day)).get("points") or []
    return estimate_curtailment(
        points,
        capacity_kw=config.get("capacity_kw"),
    )


CALIBRATION_DAYS = 30
# Store daily totals only when at least 95% of daytime samples are covered.
MIN_HISTORY_MINUTES = 684


def satellite_location(runtime: AppRuntime) -> tuple[float, float] | None:
    latest = runtime.latest or {}
    coords = latest.get("lat"), latest.get("lon")
    if all(satellite.finite(value) for value in coords):
        return coords
    local = runtime.config.get("local") or {}
    coords = local.get("lat"), local.get("lon")
    return coords if all(satellite.finite(value) for value in coords) else None


def _gain(gains, day):
    start = (date.fromisoformat(day) - timedelta(days=CALIBRATION_DAYS)).isoformat()
    prior = [value for key, value in gains.items() if start <= key < day and value is not None]
    return median(prior) if len(prior) >= 2 else None


def _estimate_satellite(curve, radiation, day, gain, capacity):
    points = curve.get("points") or []
    report = satellite.estimate(satellite.intervals(points, radiation, day), gain, capacity)
    lost = report["covered_loss_kwh"]
    return {
        "lost_kwh": lost,
        "full_at": min((p["t"] for p in points if satellite.finite(p.get("soc")) and p["soc"] >= 98), default=None),
        "actual_kwh": curve.get("generation_kwh"),
        "potential_kwh": None,
        "covered_minutes": report["covered_minutes"],
    }


async def _live_satellite(runtime, provider, day):
    location = satellite_location(runtime)
    if location is None:
        return {}
    start = (date.fromisoformat(day) - timedelta(days=CALIBRATION_DAYS)).isoformat()
    gain = _gain(runtime.store.satellite_gains(start, day), day)
    if gain is None:
        return {}
    async with runtime.satellite_lock:
        cached = runtime.satellite_today
        if cached is None or cached[0] != day or monotonic() - cached[1] >= 600:
            radiation = await satellite.fetch_radiation(*location, day, day)
            runtime.satellite_today = (day, monotonic(), radiation)
        else:
            radiation = cached[2]
    curve = await provider.fetch_day_curve(day)
    return _estimate_satellite(curve, radiation, day, gain, runtime.config.get("capacity_kw"))


async def backfill_satellite(runtime: AppRuntime) -> int:
    location = satellite_location(runtime)
    if location is None:
        return 0
    today = datetime.now(VN_TZ).date()
    first = today - timedelta(days=BACKFILL_DAYS)
    start = (first - timedelta(days=CALIBRATION_DAYS)).isoformat()
    end = (today - timedelta(days=1)).isoformat()
    gains = runtime.store.satellite_gains(start, today.isoformat())
    have = runtime.store.curtailment_days()
    pending = [row["day"] for row in runtime.store.daily(BACKFILL_DAYS + CALIBRATION_DAYS + 1)
               if start <= row["day"] <= end and
               (row["day"] not in gains or (row["day"] >= first.isoformat() and row["day"] not in have))]
    if not pending:
        return 0
    radiation = await satellite.fetch_radiation(*location, min(pending), max(pending))
    written = 0
    for day in sorted(pending):
        bins = list(satellite.intervals([], radiation, day))
        if not any(satellite.finite(sun) for sun, _ in bins):
            continue
        try:
            curve = await runtime.history_provider.fetch_day_curve(day)
        except Exception as error:
            print(f"  [curtailment] SEMS curve unavailable for {day}: {type(error).__name__}", flush=True)
            continue
        finally:
            await asyncio.sleep(REQUEST_PAUSE_SECONDS)
        points = curve.get("points") or []
        if not points:
            continue
        bins = list(satellite.intervals(points, radiation, day))
        gain = satellite.daily_gain(bins)
        complete_bins = sum(satellite.finite(sun) and all(map(satellite.valid, samples))
                            for sun, samples in bins)
        if gain is not None or complete_bins * 10 >= MIN_HISTORY_MINUTES:
            runtime.store.record_satellite_gain(day, gain)
            gains[day] = gain
        if day >= first.isoformat():
            estimate = _estimate_satellite(curve, radiation, day, _gain(gains, day),
                                           runtime.config.get("capacity_kw"))
            if estimate["covered_minutes"] >= MIN_HISTORY_MINUTES:
                runtime.store.record_curtailment(day, estimate["lost_kwh"], estimate["full_at"])
                written += 1
    return written


async def build_curtailment(runtime: AppRuntime) -> dict[str, Any]:
    """Wasted sun today (computed live) + the 30-day total (stored by the backfill)."""
    provider = runtime.history_provider
    if not supports_day_curve(provider):
        return {"supported": False}

    today = datetime.now(VN_TZ).date().isoformat()
    use_satellite = getattr(provider, "name", None) == "cloud"
    try:
        if use_satellite:
            estimate = await _live_satellite(runtime, provider, today)
        else:
            estimate = await curtail_for(provider, runtime.config, today)
    except Exception:
        estimate = {"lost_kwh": None, "full_at": None, "actual_kwh": None, "potential_kwh": None}

    by_day = {row["day"]: (row["lost"] or 0) for row in runtime.store.curtailment_recent(BACKFILL_DAYS)}
    if use_satellite:
        first = (date.fromisoformat(today) - timedelta(days=BACKFILL_DAYS)).isoformat()
        by_day = {day: lost for day, lost in by_day.items() if first <= day < today}
    elif estimate.get("lost_kwh") is not None:
        by_day[today] = estimate["lost_kwh"]

    start_day = int((runtime.config.get("evn") or {}).get("cycle_start_day", 1))
    return {
        "supported": True,
        "method": "satellite" if use_satellite else "half_sine",
        "currency": runtime.config.get("currency") or "VND",
        "marginal": marginal_price(runtime.store, runtime.tariff, start_day),
        "valuation_basis": "hypothetical_grid_reduction_at_projected_cycle_use",
        "today_grid_reduction_value": None if estimate.get("lost_kwh") is None else grid_reduction_value(runtime.store, runtime.tariff, estimate["lost_kwh"], start_day),
        "today": {
            "lost_kwh": estimate.get("lost_kwh"),
            "full_at": estimate.get("full_at"),
            "actual_kwh": estimate.get("actual_kwh"),
            "potential_kwh": estimate.get("potential_kwh"),
            "covered_minutes": estimate.get("covered_minutes", 0) if use_satellite else None,
        },
        "total30_kwh": round(sum(by_day.values()), 1) if by_day or not use_satellite else None,
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
