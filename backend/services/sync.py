"""Keep history.db consistent with SEMS and the EVN portal: on startup, then every 12 h.

A restart after downtime (power cut, reboot, deploy) is exactly when data goes missing,
so the first pass runs as soon as the live provider has logged in. SEMS is only re-read
as far back as the oldest missing day, instead of the full history on every start.
"""

from __future__ import annotations

import asyncio
import math
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, cast

from backend.runtime import AppRuntime
from backend.services.curtailment import backfill_curtailment
from providers.base import VN_TZ


SYNC_INTERVAL_SECONDS = 12 * 3600
# Give the first poll (provider login) this long before syncing anyway.
STARTUP_WAIT_SECONDS = 60
DEFAULT_FULL_MONTHS = 18
# Re-read at least this much so late SEMS corrections to recent days land.
MIN_WINDOW_MONTHS = 2
KEEP_SAMPLE_DAYS = 30
# Pause between SEMS day-curve requests to avoid the rate limit (GY0429).
REQUEST_PAUSE_SECONDS = 0.8
EVN_RECENT_DAYS = 45


def sync_window_months(rows: list[dict[str, Any]], today: date, full_months: int) -> int:
    """Months of SEMS history to re-read so `daily` has no holes up to yesterday."""
    have = {row["day"] for row in rows if row.get("kwh") is not None and row.get("cons") is not None}
    if not have:
        return full_months

    day = date.fromisoformat(min(have))
    yesterday = today - timedelta(days=1)
    while day <= yesterday and day.isoformat() in have:
        day += timedelta(days=1)
    if day > yesterday:
        return MIN_WINDOW_MONTHS
    return max(MIN_WINDOW_MONTHS, min(full_months, math.ceil((today - day).days / 31) + 1))


async def sync_daily(runtime: AppRuntime) -> dict[str, int]:
    provider = runtime.history_provider
    fetch_history = getattr(provider, "fetch_daily_history", None)
    if not callable(fetch_history):
        return {"months": 0, "days": 0, "energy_days": 0}

    store = runtime.store
    today = datetime.now(VN_TZ).date()
    full_months = int(runtime.config.get("backfill_months", DEFAULT_FULL_MONTHS))
    months = sync_window_months(store.daily_full(4000), today, full_months)

    rows = await cast(Callable[..., Awaitable[dict]], fetch_history)(months=months)
    store.backfill_daily(rows)
    energy: dict = {}
    fetch_energy = getattr(provider, "fetch_daily_energy", None)
    if callable(fetch_energy):
        energy = await cast(Callable[..., Awaitable[dict]], fetch_energy)(months=months)
        store.backfill_energy(energy)
    return {"months": months, "days": len(rows), "energy_days": len(energy)}


async def fill_sample_gaps(runtime: AppRuntime) -> int:
    """Patch holes in yesterday's and today's minute curve from the SEMS 5-minute curve.

    While the host is down no samples are recorded, so the intraday chart would disagree
    with the daily totals. Older days are pruned anyway, so they are not worth the calls.
    """
    fetch_curve = getattr(runtime.history_provider, "fetch_day_curve", None)
    if not callable(fetch_curve):
        return 0
    today = datetime.now(VN_TZ).date()
    total = 0
    for day in ((today - timedelta(days=1)).isoformat(), today.isoformat()):
        try:
            curve = await cast(Callable[[str], Awaitable[dict]], fetch_curve)(day)
            total += runtime.store.backfill_samples(day, curve.get("points") or [])
        except Exception as error:
            print(f"  [sync] samples {day}: {type(error).__name__}: {error}", flush=True)
        await asyncio.sleep(REQUEST_PAUSE_SECONDS)
    return total


async def sync_once(runtime: AppRuntime) -> dict[str, Any]:
    """One full consistency pass, recorded in runtime.last_sync.

    Each step is independent: one failing does not stop the rest.
    """
    async with runtime.sync_lock:
        started = datetime.now(VN_TZ)
        result: dict[str, Any] = {"started_at": started.isoformat(timespec="seconds"), "errors": []}

        async def step(name: str, run: Callable[[], Awaitable[Any]]) -> Any:
            try:
                return await run()
            except Exception as error:
                result["errors"].append(name)
                print(f"  [sync] {name}: {type(error).__name__}: {error}", flush=True)
                return None

        daily = await step("sems_daily", lambda: sync_daily(runtime))
        if daily and daily["months"]:
            result["sems_months"] = daily["months"]
            print(
                f"  [sync] SEMS {daily['months']} months: {daily['days']} generation days, "
                f"{daily['energy_days']} usage days; {runtime.store.daily_count()} days stored",
                flush=True,
            )

        filled = await step("samples", lambda: fill_sample_gaps(runtime))
        result["samples_filled"] = filled or 0
        if filled:
            print(f"  [sync] filled {filled} missing minute samples", flush=True)

        written = await step(
            "curtailment",
            lambda: backfill_curtailment(runtime.store, runtime.history_provider, runtime.config),
        )
        result["curtailment_days"] = written or 0
        if written:
            print(f"  [sync] wasted sun updated for {written} days", flush=True)

        async def prune() -> None:
            runtime.store.prune(keep_days=KEEP_SAMPLE_DAYS)

        await step("prune", prune)

        finished = datetime.now(VN_TZ)
        result["finished_at"] = finished.isoformat(timespec="seconds")
        result["seconds"] = round((finished - started).total_seconds())
        runtime.last_sync = result
        return result


async def _wait_for_first_poll(runtime: AppRuntime) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + STARTUP_WAIT_SECONDS
    while runtime.latest is None and loop.time() < deadline:
        await asyncio.sleep(1)


async def sync_loop(runtime: AppRuntime) -> None:
    await _wait_for_first_poll(runtime)
    while True:
        try:
            await sync_once(runtime)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"  [sync] error: {type(error).__name__}: {error}", flush=True)
        runtime.synced.set()
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


# ---------- EVN customer portal (real meter readings + bills) ----------

def build_evn_portal(config: dict[str, Any]):
    """EvnPortal from config.evn.portal when enabled with credentials, otherwise None."""
    portal = (config.get("evn") or {}).get("portal") or {}
    if not portal.get("enabled"):
        return None
    if not (portal.get("customer_id") and portal.get("username") and portal.get("password")):
        return None
    from providers.evn_portal import EvnPortal

    return EvnPortal(
        customer_id=portal["customer_id"],
        username=portal["username"],
        password=portal["password"],
        base_url=portal.get("base_url", "https://cskh.evnhcmc.vn"),
        backfill_start_year=int(portal.get("backfill_start_year", 2022)),
    )


async def evn_sync_once(runtime: AppRuntime, portal) -> dict[str, int]:
    """Full backfill the first time (empty tables), a recent window after that."""
    store = runtime.store
    if store.evn_counts()["daily"] == 0:
        return await portal.backfill(store)

    last = max((row["day"] for row in store.evn_daily_all()), default=None)
    gap = (datetime.now(VN_TZ).date() - date.fromisoformat(last)).days if last else EVN_RECENT_DAYS
    return await portal.sync_recent(store, days=max(EVN_RECENT_DAYS, gap + 7))


async def evn_loop(runtime: AppRuntime) -> None:
    portal = build_evn_portal(runtime.config)
    if portal is None:
        return
    try:
        await _wait_for_first_poll(runtime)
        while True:
            try:
                result = await evn_sync_once(runtime, portal)
                print(
                    f"  [sync] EVN {result['days']} days + {result['bills']} bills; "
                    f"{runtime.store.evn_counts()} stored",
                    flush=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                print(f"  [sync] EVN: {type(error).__name__}: {error}", flush=True)
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)
    finally:
        try:
            await portal.close()
        except Exception:
            pass
