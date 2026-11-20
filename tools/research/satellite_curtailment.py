"""Replay Wasted Sun from cached SEMS and satellite curves without writing to the app.

Run: python -m tools.research.satellite_curtailment CACHE YYYY-MM-DD --capacity-kw 16
CACHE contains YYYY-MM-DD.json (SEMS day response) and YYYY-MM-DD.sat (Open-Meteo
native 10-minute hourly object with time and shortwave_radiation in Vietnam time).
Only earlier paired dates are used for calibration. Output covers 06:00–18:00.
"""
import argparse
import json
from pathlib import Path
from statistics import median


from providers.satellite_curtailment import daily_gain, estimate, finite
from providers.satellite_curtailment import intervals as satellite_intervals


def intervals(cache, day):
    points = json.loads((cache / f"{day}.json").read_text())["points"]
    satellite = json.loads((cache / f"{day}.sat").read_text())
    radiation = dict(zip(satellite["time"], satellite["shortwave_radiation"], strict=True))
    return satellite_intervals(points, radiation, day)


def calibrate(cache, target):
    daily = []
    for file in sorted(cache.glob("????-??-??.sat")):
        if file.stem < target and file.with_suffix(".json").exists():
            gain = daily_gain(intervals(cache, file.stem))
            if gain is not None:
                daily.append(gain)
    return (median(daily) if len(daily) >= 2 else None), len(daily)


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
