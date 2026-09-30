"""AI assistant: the home's data snapshot, the lookup tools and user-confirmed actions."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, Awaitable, Callable, cast

from backend.runtime import AppRuntime
from backend.services.curtailment import marginal_price
from backend.services.history_summary import compute_records, compute_stats
from backend.services.money import build_money
from providers import report as report_mod
from providers.base import VN_TZ


RESERVE_MIN_PCT = 10
RESERVE_MAX_PCT = 80
MAX_RANGE_DAYS = 190


def _round(value: Any, digits: int = 1) -> Any:
    return None if value is None else round(value, digits)


def _cycle_start_day(runtime: AppRuntime) -> int:
    return int((runtime.config.get("evn") or {}).get("cycle_start_day", 1))


def _upcoming_forecast(runtime: AppRuntime, today: str, days: int) -> list[dict[str, Any]] | None:
    forecaster = runtime.forecaster
    if not forecaster.ready:
        return None
    weather = {row["day"]: row for row in runtime.store.weather_all()}
    wanted = [day for day in [today] + [d for d in sorted(weather) if d > today][:days] if day in weather]
    return [
        {"day": p["date"], "generation_kwh": _round(p.get("kwh"))}
        for p in forecaster.predict_days(weather, wanted)
    ]


def build_context(runtime: AppRuntime) -> dict[str, Any]:
    """Real numbers of the home for the model. Only built per chat turn, never on the poll path."""
    now = datetime.now(VN_TZ)
    today = now.date()
    store = runtime.store
    latest = runtime.latest or {}
    rows = store.daily_full(400)
    currency = runtime.config.get("currency") or "VND"
    stats = compute_stats(store.daily(400), runtime.config.get("price_per_kwh"), currency)
    try:
        money = build_money(runtime, today)
    except Exception:
        money = {}
    cycle = money.get("cycle") or {}
    tier = money.get("tier") or {}
    try:
        forecast = _upcoming_forecast(runtime, today.isoformat(), 3)
    except Exception:
        forecast = None

    return {
        "now": now.strftime("%Y-%m-%d %H:%M"),
        "system": {
            "pv_kwp": runtime.config.get("capacity_kw"),
            "battery_kwh": latest.get("battery_capacity_kwh"),
            "battery_reserve_pct": runtime.config.get("battery_reserve_percent"),
            "location": "Ho Chi Minh City",
            "tariff": "EVN tiered price rising with monthly usage, plus 8% VAT",
        },
        "live": {
            "pv_w": latest.get("pv_power_w"),
            "load_w": latest.get("load_power_w"),
            "battery_pct": latest.get("battery_soc"),
            "battery_w": latest.get("battery_power_w"),
            "grid_w": latest.get("grid_power_w"),
            "status": latest.get("status"),
        },
        "today": {
            "generation_kwh": latest.get("today_energy_kwh"),
            "consumption_kwh": latest.get("today_consumption_kwh"),
            "grid_buy_kwh": latest.get("today_buy_kwh"),
            "saved_vnd": (money.get("today") or {}).get("saved"),
        },
        "this_bill_cycle": {
            "start": cycle.get("start"),
            "grid_buy_kwh": cycle.get("buy_kwh"),
            "bill_so_far_vnd": cycle.get("bill_now"),
            "bill_projected_vnd": cycle.get("bill_proj"),
            "savings_projected_vnd": cycle.get("saved_proj"),
            # No tier index on purpose: the model then says "tier 4", which the persona forbids.
            "kwh_before_next_price_level": tier.get("to_next_kwh"),
            "last_real_evn_bill": money.get("evn_bill"),
        },
        "stats": {
            "avg30_kwh": stats.get("avg30_kwh"),
            "month_kwh": stats.get("month_kwh"),
            "total_kwh": stats.get("total_kwh"),
            "days": stats.get("days"),
        },
        "recent_months": [
            {"month": r["month"], "generation_kwh": _round(r.get("kwh")), "grid_buy_kwh": _round(r.get("buy"))}
            for r in store.monthly(13)
        ],
        "recent_days": [
            {"day": r["day"], "generation_kwh": _round(r.get("kwh")),
             "consumption_kwh": _round(r.get("cons")), "grid_buy_kwh": _round(r.get("buy"))}
            for r in rows[-30:]
        ],
        "records": compute_records(rows),
        "forecast": {"next_days": forecast, "night_need_kwh": store.night_load_avg_kwh(14)},
        "recent_notices": [
            {"at": n["ts"], "kind": n["kind"], "data": n["data"]} for n in store.notices_recent(8)
        ],
        "currency": currency,
    }


def _iso(value: Any, name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except Exception:
        raise ValueError(f"{name} must be YYYY-MM-DD")


def _hourly_from_curve(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """5-minute curve -> 24 hourly averages, enough for "was the battery full at noon"."""
    hours: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        hour = str(point.get("t") or "")[:2]
        if hour:
            hours.setdefault(hour, []).append(point)

    def avg(items: list[dict[str, Any]], key: str) -> int | None:
        values = [item[key] for item in items if item.get(key) is not None]
        return round(sum(values) / len(values)) if values else None

    return [
        {"hour": int(hour), "pv_w": avg(items, "pv"), "load_w": avg(items, "load"),
         "grid_w": avg(items, "grid"), "battery_w": avg(items, "batt"), "soc_pct": avg(items, "soc")}
        for hour, items in sorted(hours.items())
    ]


Tool = dict[str, Any]


def build_tools(runtime: AppRuntime, action_sink: list[dict[str, Any]]) -> dict[str, Tool]:
    """Function-calling registry: {name: {"decl": Gemini functionDeclaration, "fn": async(args) -> dict}}.

    Every tool only reads data, except propose_action, which queues a suggestion that the
    user must confirm in the UI (/api/action). The model can never change anything itself.
    """
    store = runtime.store
    provider = runtime.history_provider

    async def get_day_detail(args: dict) -> dict:
        day = _iso(args.get("date"), "date").isoformat()
        row = next((r for r in store.daily_full(4000) if r["day"] == day), None) or {}
        out: dict[str, Any] = {
            "date": day,
            "generation_kwh": row.get("kwh"),
            "consumption_kwh": row.get("cons"),
            "grid_buy_kwh": row.get("buy"),
        }
        wasted = next((r for r in store.curtailment_recent(400) if r["day"] == day), None)
        if wasted:
            out["wasted_sun_kwh"] = wasted.get("lost")
            out["battery_full_at"] = wasted.get("full_at")
        weather = next((r for r in store.weather_all() if r["day"] == day), None)
        if weather:
            out["weather"] = {"rain_mm": weather.get("precip"), "tmax_c": weather.get("tmax"),
                              "radiation": weather.get("rad")}
        fetch_curve = getattr(provider, "fetch_day_curve", None)
        if callable(fetch_curve):
            try:
                curve = await cast(Callable[[str], Awaitable[dict]], fetch_curve)(day)
                out["hourly"] = _hourly_from_curve(curve.get("points") or [])
            except Exception:
                out["hourly"] = None
        return out

    async def get_daily_history(args: dict) -> dict:
        start, end = _iso(args.get("start"), "start"), _iso(args.get("end"), "end")
        if end < start:
            start, end = end, start
        if (end - start).days > MAX_RANGE_DAYS:
            raise ValueError(f"range is limited to {MAX_RANGE_DAYS} days")
        rows = [r for r in store.daily_full(4000) if start.isoformat() <= r["day"] <= end.isoformat()]

        def total(key: str) -> float | None:
            values = [r[key] for r in rows if r.get(key) is not None]
            return round(sum(values), 1) if values else None

        return {
            "start": start.isoformat(), "end": end.isoformat(), "days_with_data": len(rows),
            "total_generation_kwh": total("kwh"), "total_consumption_kwh": total("cons"),
            "total_grid_buy_kwh": total("buy"),
            "daily": [{"day": r["day"], "gen": _round(r.get("kwh")), "cons": _round(r.get("cons")),
                       "buy": _round(r.get("buy"))} for r in rows],
        }

    async def get_cycle_report(args: dict) -> dict:
        offset = max(1, min(int(args.get("offset") or 1), 120))
        today = datetime.now(VN_TZ).date()
        start_day = _cycle_start_day(runtime)
        cycle_start, _ = report_mod.closed_cycle_bounds(today, start_day, offset)
        return report_mod.compute_report(
            store.daily_full(max(400, store.daily_count())),
            store.curtailment_recent((today - cycle_start).days + 40),
            store.evn_bills_all(), runtime.tariff, today, start_day, offset,
        )

    async def get_curtailment(args: dict) -> dict:
        days = max(1, min(int(args.get("days") or 30), 60))
        rows = store.curtailment_recent(days)
        marginal = marginal_price(store, runtime.tariff)
        total = round(sum((r.get("lost") or 0) for r in rows), 1)
        return {"days": days, "total_lost_kwh": total, "value_vnd": round(total * marginal),
                "marginal_vnd_per_kwh": marginal,
                "daily": [{"day": r["day"], "lost_kwh": r.get("lost"), "battery_full_at": r.get("full_at")}
                          for r in rows]}

    async def get_weather_forecast(args: dict) -> dict:
        today = datetime.now(VN_TZ).date().isoformat()
        weather = [r for r in store.weather_all() if r["day"] >= today][:8]
        predicted: dict[str, Any] = {}
        if runtime.forecaster.ready:
            by_day = {r["day"]: r for r in weather}
            predicted = {p["date"]: p.get("kwh") for p in runtime.forecaster.predict_days(by_day, list(by_day))}
        return {"days": [{"day": r["day"], "rain_mm": r.get("precip"), "rain_prob_pct": r.get("rain_prob"),
                          "tmax_c": r.get("tmax"), "predicted_generation_kwh": predicted.get(r["day"])}
                         for r in weather],
                "night_load_kwh": store.night_load_avg_kwh(14)}

    async def get_hourly_profile(args: dict) -> dict:
        return {"hours": store.hourly_profile(30),
                "note": "30-day average; pv/load/grid in W; grid > 0 buys, < 0 sells"}

    async def propose_action(args: dict) -> dict:
        kind = str(args.get("action") or "")
        if kind != "set_reserve":
            raise ValueError("only action=set_reserve is supported")
        pct = int(float(args.get("reserve_pct") or 0))
        if not RESERVE_MIN_PCT <= pct <= RESERVE_MAX_PCT:
            raise ValueError(f"reserve_pct must be {RESERVE_MIN_PCT}..{RESERVE_MAX_PCT}")
        current = float(runtime.config.get("battery_reserve_percent", 20))
        action_sink.append({"kind": kind, "params": {"reserve_pct": pct}, "current": current,
                            "reason": str(args.get("reason") or "")[:300]})
        return {"ok": True, "queued_for_user_confirmation": True,
                "current_reserve_pct": current, "proposed_reserve_pct": pct}

    obj, string, integer, number = "object", "string", "integer", "number"
    return {
        "get_day_detail": {"fn": get_day_detail, "decl": {
            "name": "get_day_detail",
            "description": "Details of ONE day: generation, consumption, grid purchase, wasted sun, weather and the HOURLY course (pv/load/battery/grid/battery %). Use when the user asks about a specific day.",
            "parameters": {"type": obj, "properties": {"date": {"type": string, "description": "YYYY-MM-DD"}},
                           "required": ["date"]}}},
        "get_daily_history": {"fn": get_daily_history, "decl": {
            "name": "get_daily_history",
            "description": f"Generation, consumption and grid purchase PER DAY over a date range (max {MAX_RANGE_DAYS} days) plus totals. Use to compare weeks or months, find unusual days, or answer about periods beyond the last 30 days.",
            "parameters": {"type": obj, "properties": {"start": {"type": string, "description": "YYYY-MM-DD"},
                                                       "end": {"type": string, "description": "YYYY-MM-DD"}},
                           "required": ["start", "end"]}}},
        "get_cycle_report": {"fn": get_cycle_report, "decl": {
            "name": "get_cycle_report",
            "description": "Report of a CLOSED EVN billing cycle: generation, consumption, purchase, estimated cost, the real EVN bill, and the change vs the cycle before. offset=1 is the latest closed cycle, 2 the one before.",
            "parameters": {"type": obj, "properties": {"offset": {"type": integer, "description": "1 = latest closed cycle"}},
                           "required": ["offset"]}}},
        "get_curtailment": {"fn": get_curtailment, "decl": {
            "name": "get_curtailment",
            "description": "WASTED sun (battery full, power not used) per day over the last N days, and its value in money.",
            "parameters": {"type": obj, "properties": {"days": {"type": integer, "description": "default 30, max 60"}}}}},
        "get_weather_forecast": {"fn": get_weather_forecast, "decl": {
            "name": "get_weather_forecast",
            "description": "Weather and predicted generation for the next days (rain, temperature, kWh) and the usual night-time need.",
            "parameters": {"type": obj, "properties": {}}}},
        "get_hourly_profile": {"fn": get_hourly_profile, "decl": {
            "name": "get_hourly_profile",
            "description": "Average 24-hour profile over 30 days (W generated/used/bought per hour), for questions about the best time to use power.",
            "parameters": {"type": obj, "properties": {}}}},
        "propose_action": {"fn": propose_action, "decl": {
            "name": "propose_action",
            "description": f"SUGGEST a settings change for the user to confirm (never applied by you). Supported: action='set_reserve' changes the battery reserve (%) the dashboard uses in its estimates. Only call when the benefit is CLEAR, and explain why.",
            "parameters": {"type": obj, "properties": {
                "action": {"type": string, "description": "set_reserve"},
                "reserve_pct": {"type": number, "description": f"{RESERVE_MIN_PCT}..{RESERVE_MAX_PCT}"},
                "reason": {"type": string, "description": "short reason, in the language of the chat"}},
                "required": ["action", "reserve_pct", "reason"]}}},
    }


def apply_action(runtime: AppRuntime, kind: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run an action the USER confirmed. Hard whitelist, bounded values.

    set_reserve changes battery_reserve_percent for the dashboard's own estimates; it does
    not write to the inverter. Persisted to config.json only when that file is the loaded one.
    """
    if kind != "set_reserve":
        raise ValueError("unknown_action")
    pct = int(float(params.get("reserve_pct") or 0))
    if not RESERVE_MIN_PCT <= pct <= RESERVE_MAX_PCT:
        raise ValueError("out_of_range")
    old = float(runtime.config.get("battery_reserve_percent", 20))

    path = runtime.root / "config.json"
    if runtime.config.get("_file") == "config.json" and path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["battery_reserve_percent"] = pct
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    runtime.config["battery_reserve_percent"] = pct
    for provider in {id(p): p for p in (runtime.live_provider, runtime.history_provider)}.values():
        if hasattr(provider, "battery_reserve_percent"):
            setattr(provider, "battery_reserve_percent", float(pct))
    print(f"  [action] set_reserve: {old} -> {pct}%", flush=True)
    return {"ok": True, "kind": kind, "old": old, "new": pct}
