"""Replay Wasted Sun from cached SEMS and satellite curves without writing to the app.

Run: python -m tools.research.satellite_curtailment CACHE YYYY-MM-DD --capacity-kw 16
CACHE contains YYYY-MM-DD.json (SEMS day response) and YYYY-MM-DD.sat (Open-Meteo
native 10-minute hourly object with time and shortwave_radiation in Vietnam time).
Only earlier paired dates are used for calibration. Output covers 06:00–18:00.
"""
import argparse
import json
import math
from pathlib import Path
from statistics import median


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def intervals(cache, day):
    points = json.loads((cache / f"{day}.json").read_text())["points"]
    satellite = json.loads((cache / f"{day}.sat").read_text())
    radiation = dict(zip(satellite["time"], satellite["shortwave_radiation"], strict=True))
    by_clock = {p["t"]: p for p in points}

    def clock(minute):
        return f"{minute // 60:02}:{minute % 60:02}"

    for end in range(370, 1081, 10):
        # Match the preceding ten minutes to two five-minute samples.
        samples = [by_clock.get(clock(m)) for m in (end - 5, end)]
        yield radiation.get(f"{day}T{clock(end)}"), samples


def valid(p):
    return p is not None and all(finite(p.get(k)) for k in ("pv", "load", "batt", "soc", "grid"))


def calibrate(cache, target):
    daily = []
    for file in sorted(cache.glob("????-??-??.sat")):
        if file.stem >= target or not file.with_suffix(".json").exists():
            continue
        ratios = []
        for sun, samples in intervals(cache, file.stem):
            if finite(sun) and sun >= 100 and all(
                valid(p) and p["soc"] < 90 and p["batt"] > 300 and abs(p["grid"]) <= 200
                for p in samples
            ):
                ratios.append(sum(p["pv"] for p in samples) / (2 * sun))
        if ratios:
            daily.append(median(ratios))
    return (median(daily) if len(daily) >= 2 else None), len(daily)


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
                available = min(capacity_kw * 1000, gain * sun)
                loss += max(0, available - p["pv"]) / 12000
    return {"covered_loss_kwh": round(loss, 2) if covered else None,
            "covered_minutes": covered, "missing_minutes": missing}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("day")
    parser.add_argument("--capacity-kw", type=float, required=True)
    args = parser.parse_args()
    if not finite(args.capacity_kw) or args.capacity_kw <= 0:
        parser.error("capacity must be positive and finite")
    gain, days = calibrate(args.cache, args.day)
    result = estimate(intervals(args.cache, args.day), gain, args.capacity_kw)
    print(json.dumps({"day": args.day, "calibration_days": days, **result}, indent=2))
