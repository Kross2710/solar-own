"""Live metric collection, fallback, persistence, and shutdown."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from backend.runtime import AppRuntime
from providers.base import VN_TZ


async def snapshot(runtime: AppRuntime) -> dict[str, Any]:
    metrics = (await runtime.live_provider.get_metrics()).to_dict()

    if runtime.push_alerts is not None:
        runtime.push_alerts.observe(metrics)

    fell_back = False
    if (
        metrics.get("status") == "offline"
        and runtime.history_provider is not runtime.live_provider
    ):
        try:
            fallback = (await runtime.history_provider.get_metrics()).to_dict()
            if fallback.get("status") != "offline":
                metrics = fallback
                fell_back = True
        except Exception:
            pass

    if fell_back and not runtime.live_fallback_on:
        print("  [backup] live provider offline, using history provider for metrics")
        runtime.live_fallback_on = True
    elif (
        not fell_back
        and runtime.live_fallback_on
        and metrics.get("status") != "offline"
    ):
        print("  [backup] live provider back online, resuming live metrics")
        runtime.live_fallback_on = False

    if metrics.get("status") != "offline" and (
        metrics.get("meter_total_buy_kwh") is not None
        or metrics.get("meter_total_sell_kwh") is not None
    ):
        day = (
            str(metrics.get("timestamp"))[:10]
            or datetime.now(VN_TZ).date().isoformat()
        )
        buy, sell = runtime.store.meter_today(
            day,
            metrics.get("meter_total_buy_kwh"),
            metrics.get("meter_total_sell_kwh"),
        )
        if buy is not None:
            metrics["today_buy_kwh"] = buy
        if sell is not None:
            metrics["today_sell_kwh"] = sell

    # Documented key for the polling cadence; retain the historical misspelling
    # as a backward-compatible alias so existing consumers keep working.
    cadence = (
        runtime.poll_interval if metrics.get("source") == "local" else 60
    )
    metrics["poll_interval_seconds"] = cadence
    metrics["poll_inverval_seconds"] = cadence
    runtime.latest = metrics

    if metrics.get("status") != "offline":
        runtime.store.record(metrics)

    return metrics


# Throttle live-poll error logging so a persistently offline inverter (local
# polls every 10s) can't spam the log; recovery is still surfaced at once.
POLL_ERROR_LOG_EVERY = 300


async def poll_loop(runtime: AppRuntime) -> None:
    last_error: datetime | None = None
    down = False
    while True:
        try:
            await snapshot(runtime)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # snapshot() itself failing (providers normally return status=offline,
            # so this path is rare). Throttle so a broken call can't spam the log.
            now = datetime.now(VN_TZ)
            if last_error is None or (now - last_error).total_seconds() >= POLL_ERROR_LOG_EVERY:
                last_error = now
                print(f"  [poll] error: {type(error).__name__}: {error}", flush=True)
            down = True
        else:
            # An outage is signalled by status, not an exception: a live provider
            # that can't reach the inverter returns "offline"/"error", and snapshot()
            # flips live_fallback_on when it starts serving from the history provider.
            now_down = runtime.live_fallback_on or (
                runtime.latest is not None
                and runtime.latest.get("status") in ("offline", "error")
            )
            if now_down and not down:
                print("  [poll] live provider offline", flush=True)
            elif not now_down and down:
                print("  [poll] recovered: live provider back online", flush=True)
                last_error = None  # reset throttle so a later outage isn't suppressed
            down = now_down
        await asyncio.sleep(runtime.poll_interval)


async def close_providers(runtime: AppRuntime) -> None:
    seen: set[int] = set()
    for provider in (runtime.live_provider, runtime.history_provider):
        if id(provider) in seen:
            continue
        seen.add(id(provider))
        try:
            await provider.close()
        except Exception:
            pass
