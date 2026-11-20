"""Estimate unused PV with independent satellite irradiance and inverter samples."""
from statistics import median
import math


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def intervals(points, radiation, day):
    by_clock = {p["t"]: p for p in points}

    def clock(minute):
        return f"{minute // 60:02}:{minute % 60:02}"

    for end in range(370, 1081, 10):
        # Match the preceding ten minutes to two five-minute samples.
        samples = [by_clock.get(clock(m)) for m in (end - 5, end)]
        yield radiation.get(f"{day}T{clock(end)}"), samples


def valid(p):
    return p is not None and all(finite(p.get(k)) for k in ("pv", "load", "batt", "soc", "grid"))


def daily_gain(bins):
    ratios = [
        sum(p["pv"] for p in samples) / (2 * sun)
        for sun, samples in bins
        if finite(sun) and sun >= 100 and all(
            valid(p) and p["soc"] < 90 and p["batt"] > 300 and abs(p["grid"]) <= 200
            for p in samples
        )
    ]
    return median(ratios) if ratios else None


def estimate(bins, gain, capacity_kw):
    loss = 0.0
    covered = missing = 0
    for sun, samples in bins:
        for p in samples:
            if not valid(p) or not finite(sun) or sun < 0 or gain is None:
                missing += 5
                continue
            covered += 5
            if (p["soc"] >= 95 and abs(p["batt"]) <= 200 and abs(p["grid"]) <= 200
                    and abs(p["pv"] - p["load"]) <= 300):
                available = gain * sun
                if finite(capacity_kw) and capacity_kw > 0:
                    available = min(capacity_kw * 1000, available)
                loss += max(0, available - p["pv"]) / 12000
    return {"covered_loss_kwh": round(loss, 2) if covered else None,
            "covered_minutes": covered, "missing_minutes": missing}


async def fetch_radiation(lat, lon, start, end):
    import httpx

    params = {
        "latitude": round(lat, 2), "longitude": round(lon, 2),
        "start_date": start, "end_date": end,
        "timezone": "Asia/Ho_Chi_Minh",
        "hourly": "shortwave_radiation",
        "models": "satellite_radiation_seamless",
        "temporal_resolution": "native",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get("https://satellite-api.open-meteo.com/v1/archive", params=params)
        response.raise_for_status()
    hourly = response.json()["hourly"]
    return dict(zip(hourly["time"], hourly["shortwave_radiation"], strict=True))
