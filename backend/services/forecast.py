"""Solar yield forecast: weather ingestion, model training and the /api/forecast payload."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from backend.runtime import AppRuntime
from providers import forecast as fc_mod
from providers.base import VN_TZ


REFRESH_SECONDS = 12 * 3600
# Until the first poll delivers the site's lat/lon, retry often.
WAIT_FOR_LOCATION_SECONDS = 30
WAIT_FOR_SYNC_SECONDS = 10 * 60
MIN_TRAINING_DAYS = 20


def _location(runtime: AppRuntime) -> tuple[float | None, float | None]:
    latest = runtime.latest or {}
    return latest.get("lat"), latest.get("lon")


async def refresh_forecast(runtime: AppRuntime) -> bool:
    """Fetch weather (archive for history + forecast for the next days), then retrain.

    The archive API covers the whole history consistently for training; the forecast
    API provides the next 7 days and fills the few recent days the archive still lags.
    Everything is cached in weather_daily.
    """
    forecaster = runtime.forecaster
    if not forecaster.available:
        return False
    lat, lon = _location(runtime)
    if lat is None or lon is None:
        return False

    store = runtime.store
    have = [row for row in store.daily_full(4000) if row.get("kwh") is not None]
    if len(have) < MIN_TRAINING_DAYS:
        return False

    today = datetime.now(VN_TZ).date().isoformat()
    archive_rad_days: set[str] = set()
    try:
        archive = await fc_mod.fetch_archive_weather(lat, lon, have[0]["day"], today)
        store.weather_upsert(archive)
        archive_rad_days = {day for day, value in archive.items() if value.get("rad") is not None}
    except Exception as error:
        print(f"  [forecast] archive error: {type(error).__name__}: {error}", flush=True)

    try:
        forecast_weather = await fc_mod.fetch_daily_weather(
            lat, lon, today, past_days=14, forecast_days=7
        )
        # Future days stay is_fcst=1. Past days the archive has not published yet are
        # filled from the forecast as is_fcst=0 so they train now; the archive overwrites
        # them on a later cycle.
        fill: dict[str, Any] = {}
        for day, value in forecast_weather.items():
            if day > today:
                fill[day] = value
            elif day not in archive_rad_days and value.get("rad") is not None:
                fill[day] = {**value, "is_fcst": 0}
        store.weather_upsert(fill)
    except Exception as error:
        print(f"  [forecast] forecast error: {type(error).__name__}: {error}", flush=True)

    # Training is CPU-bound (numpy + sklearn bake-off): keep it off the event loop.
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(None, forecaster.fit, store.training_rows(), today)
    if ok:
        quality = forecaster.quality
        print(
            f"  [forecast] {quality['model']}: MAE {quality['mae']} kWh, "
            f"MAPE {quality['mape']}%, R² {quality['r2']}, n={quality['n_train']}",
            flush=True,
        )
    return ok


async def forecast_loop(runtime: AppRuntime) -> None:
    try:
        await asyncio.wait_for(runtime.synced.wait(), timeout=WAIT_FOR_SYNC_SECONDS)
    except asyncio.TimeoutError:
        pass
    while True:
        lat, _lon = _location(runtime)
        if lat is None:
            await asyncio.sleep(WAIT_FOR_LOCATION_SECONDS)
            continue
        try:
            async with runtime.forecast_lock:
                await refresh_forecast(runtime)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"  [forecast] error: {type(error).__name__}: {error}", flush=True)
        await asyncio.sleep(REFRESH_SECONDS)


async def build_forecast(runtime: AppRuntime) -> dict[str, Any]:
    """Next days' yield forecast + honest walk-forward model quality."""
    forecaster = runtime.forecaster
    if not forecaster.available:
        return {"ready": False, "reason": "no_numpy"}
    if not forecaster.ready:
        async with runtime.forecast_lock:
            if not forecaster.ready:
                await refresh_forecast(runtime)
    if not forecaster.ready:
        return {"ready": False, "reason": "not_enough_data"}

    store = runtime.store
    today = datetime.now(VN_TZ).date().isoformat()
    weather = {row["day"]: row for row in store.weather_all()}
    days = [today] + [day for day in sorted(weather) if day > today][:6]
    predictions = forecaster.predict_days(weather, [day for day in days if day in weather])
    for prediction in predictions:
        prediction["today"] = prediction["date"] == today

    last_30 = [row["kwh"] for row in store.daily(40) if row.get("kwh") is not None][-30:]
    return {
        "ready": True,
        "model": forecaster.model_name,
        "avg30_kwh": round(sum(last_30) / len(last_30), 1) if last_30 else None,
        "night_need_kwh": store.night_load_avg_kwh(14),
        "quality": {key: value for key, value in forecaster.quality.items() if key != "board"},
        "days": predictions,
        "updated_at": forecaster.updated_at,
    }
