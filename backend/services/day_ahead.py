"""Day-ahead planning for the zero-export installation, in Vietnam local time."""
from datetime import datetime, timedelta
from statistics import median

import httpx

from backend.services.curtailment import CALIBRATION_DAYS, satellite_location
from providers.base import VN_TZ
from providers.satellite_curtailment import finite


def simulate(pv, loads, dawn_soc, battery_kwh, charge_limit_kw):
    stored = battery_kwh * dawn_soc / 100
    reserve = battery_kwh * 0.2
    unused = []
    for available, load in zip(pv, loads, strict=True):
        balance = available - load
        if balance >= 0:
            charge = min(balance, battery_kwh - stored, charge_limit_kw)
            stored += charge
            unused.append(balance - charge)
        else:
            stored -= min(-balance, max(0, stored - reserve))
            unused.append(0.0)
    return unused


async def issue_forecast(runtime):
    now = datetime.now(VN_TZ)
    tomorrow = now.date() + timedelta(days=1)
    target = tomorrow.isoformat()
    if getattr(runtime.history_provider, "name", None) != "cloud":
        return {"ready": False, "reason": "unsupported_site"}
    async with runtime.day_ahead_lock:
        saved = runtime.store.day_ahead_snapshot(target)
        if saved:
            return saved
        location = satellite_location(runtime)
        metrics = runtime.latest or {}
        battery = metrics.get("battery_capacity_kwh")
        cap = metrics.get("capacity_kw") or runtime.config.get("capacity_kw")
        if location is None or not all(finite(x) and x > 0 for x in (cap, battery)):
            return {"ready": False, "reason": "site_data_missing"}
        start = (now.date() - timedelta(days=CALIBRATION_DAYS)).isoformat()
        end = now.date().isoformat()
        gains = [g for g in runtime.store.satellite_gains(start, end).values() if finite(g) and g > 0]
        profiles = runtime.store.day_ahead_profiles(start, end)
        similar = [p for p in profiles if p["weekend"] == (tomorrow.weekday() >= 5)]
        if len(similar) >= 3:
            profiles = similar
        if len(gains) < 2 or len(profiles) < 3:
            return {"ready": False, "reason": "insufficient_history"}

        params = dict(latitude=location[0], longitude=location[1], timezone="Asia/Ho_Chi_Minh",
                      hourly="shortwave_radiation", start_date=target, end_date=target)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            response.raise_for_status()
        hourly = response.json()["hourly"]
        radiation = dict(zip(hourly["time"], hourly["shortwave_radiation"], strict=True))
        # Radiation timestamps mark the end of the preceding hour.
        sun = [radiation.get(f"{target}T{h:02d}:00") for h in range(7, 19)]
        if not all(finite(x) and x >= 0 for x in sun):
            return {"ready": False, "reason": "radiation_missing"}
        gain = median(gains)
        pv = [min(cap, gain * x / 1000) for x in sun]
        limit = median(p["peak_charge_kw"] for p in profiles)
        if limit <= 0:
            return {"ready": False, "reason": "charge_limit_unknown"}
        runs = [simulate(pv, p["loads"], p["soc"], battery, limit) for p in profiles]
        mean_unused = [sum(samples) / len(samples) for samples in zip(*runs)]
        totals = sorted(map(sum, runs))
        peak = max(range(len(pv)), key=mean_unused.__getitem__)
        issued = datetime.now(VN_TZ)
        if issued.date() != now.date():
            return {"ready": False, "reason": "date_changed"}
        snapshot = dict(ready=True, date=target, issued_at=issued.isoformat(timespec="seconds"),
                        pv_kwh=round(sum(pv), 1), unused_kwh=round(sum(mean_unused), 1),
                        scenario_low_kwh=round(totals[0], 1), scenario_high_kwh=round(totals[-1], 1),
                        profile_days=len(runs), calibration_days=len(gains), charge_limit_kw=round(limit, 2),
                        peak_hour=peak + 6 if mean_unused[peak] >= 0.1 else None,
                        hours=[dict(hour=h + 6, pv_kw=round(power, 2), unused_kw=round(mean_unused[h], 2))
                               for h, power in enumerate(pv)])
        return runtime.store.day_ahead_snapshot(target, snapshot)


async def build_day_ahead(runtime):
    try:
        return await issue_forecast(runtime)
    except (httpx.HTTPError, KeyError, ValueError) as error:
        print(f"  [day-ahead] forecast unavailable: {type(error).__name__}", flush=True)
        return {"ready": False, "reason": "weather_unavailable"}
