"""Live metric collection, fallback, persistence, and shutdown."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from backend.runtime import AppRuntime
from providers.base import VN_TZ


async def snapshot(runtime: AppRuntime) -> dict[str, Any]:
    metrics = (await runtime.live_provider.get_metrics()).to_dict()

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

    metrics["poll_inverval_seconds"] = (
        runtime.poll_interval if metrics.get("source") == "local" else 60
    )
    runtime.latest = metrics

    if metrics.get("status") != "offline":
        runtime.store.record(metrics)

    return metrics


async def poll_loop(runtime: AppRuntime) -> None:
    while True:
        try:
            await snapshot(runtime)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
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
