"""Pure history statistics and summary aggregation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from providers.base import VN_TZ
from providers.evn import EvnTariff
from providers.history import HistoryStore


def compute_stats(
    rows: list[dict[str, Any]],
    price: float | None,
    currency: str = "VND",
) -> dict[str, Any]:
    valid_rows = [row for row in rows if row.get("kwh") is not None]
    if not valid_rows:
        return {}

    today = datetime.now(VN_TZ).date().isoformat()
    current_month = today[:7]

    def money(value: float | None) -> int | None:
        return round(value * price) if price and value is not None else None

    total_kwh = sum(row["kwh"] for row in valid_rows)
    days = len(valid_rows)
    best = max(valid_rows, key=lambda row: row["kwh"])
    today_row = next((row for row in valid_rows if row["day"] == today), None)
    previous = [row for row in valid_rows if row["day"] != today]
    worst = min(previous, key=lambda row: row["kwh"]) if previous else None
    last_30 = previous[-30:]
    average_30 = (
        sum(row["kwh"] for row in last_30) / len(last_30)
        if last_30
        else None
    )
    today_kwh = today_row["kwh"] if today_row else None
    percent = (
        round(today_kwh / average_30 * 100)
        if today_kwh and average_30
        else None
    )
    month_kwh = sum(
        row["kwh"]
        for row in valid_rows
        if row["day"][:7] == current_month
    )

    months: dict[str, float] = {}
    for row in valid_rows:
        month = row["day"][:7]
        months[month] = months.get(month, 0) + row["kwh"]

    monthly = [
        {"month": month, "kwh": round(kwh, 1), "savings": money(kwh)}
        for month, kwh in sorted(months.items())
    ]

    return {
        "today_kwh": today_kwh,
        "avg30_kwh": round(average_30, 1) if average_30 else None,
        "today_vs_avg_pct": percent,
        "best_day": {
            "day": best["day"],
            "kwh": round(best["kwh"], 1),
        },
        "worst_day": (
            {"day": worst["day"], "kwh": round(worst["kwh"], 1)}
            if worst
            else None
        ),
        "avg_per_day_kwh": round(total_kwh / days, 1) if days else None,
        "month_kwh": round(month_kwh, 1),
        "month_savings": money(month_kwh),
        "total_kwh": round(total_kwh, 1),
        "total_savings": money(total_kwh),
        "days": days,
        "monthly": monthly,
        "currency": currency,
    }


def compute_records(rows: list[dict[str, Any]]) -> dict[str, Any]:
    generation_rows = [row for row in rows if row.get("kwh") is not None]
    if not generation_rows:
        return {}

    best = max(generation_rows, key=lambda row: row["kwh"])
    records: dict[str, Any] = {
        "best_day": {
            "day": best["day"],
            "kwh": round(best["kwh"], 1),
        }
    }

    self_powered_rows = [
        row
        for row in generation_rows
        if row.get("cons")
        and row["cons"] > 0
        and row.get("buy") is not None
    ]
    if self_powered_rows:
        def self_powered_ratio(row: dict[str, Any]) -> float:
            return max(0.0, (row["cons"] - (row.get("buy") or 0)) / row["cons"])

        best_self_powered = max(self_powered_rows, key=self_powered_ratio)
        records["best_self_day"] = {
            "day": best_self_powered["day"],
            "pct": round(self_powered_ratio(best_self_powered) * 100),
        }

    months: dict[str, float] = {}
    for row in generation_rows:
        month = row["day"][:7]
        months[month] = months.get(month, 0.0) + row["kwh"]
    if months:
        peak_month = max(months, key=lambda month: months[month])
        records["peak_month"] = {
            "month": peak_month,
            "kwh": round(months[peak_month], 1),
        }

    best_streak = 0
    streak = 0
    streak_start: str | None = None
    best_start: str | None = None
    best_end: str | None = None
    previous_day: date | None = None

    for row in generation_rows:
        if not row["kwh"] or row["kwh"] <= 0:
            previous_day = None
            streak = 0
            continue

        current_day = date.fromisoformat(row["day"])
        if previous_day is not None and (current_day - previous_day).days == 1:
            streak += 1
        else:
            streak = 1
            streak_start = row["day"]

        if streak > best_streak:
            best_streak = streak
            best_start = streak_start
            best_end = row["day"]
        previous_day = current_day

    if best_streak:
        records["streak"] = {
            "days": best_streak,
            "start": best_start,
            "end": best_end,
        }

    return records


def build_summary(
    store: HistoryStore,
    tariff: EvnTariff,
    currency: str,
) -> dict[str, Any]:
    def enrich(
        rows: list[dict[str, Any]],
        key: str,
    ) -> list[dict[str, Any]]:
        enriched = []
        for row in rows:
            days = row.get("days") or 0
            covered = (
                (row.get("cons_days") or 0) >= days
                and (row.get("buy_days") or 0) >= days
            )
            saved = None
            if (
                covered
                and row.get("cons") is not None
                and row.get("buy") is not None
            ):
                saved = round(
                    tariff.savings(
                        row.get("cons") or 0,
                        row.get("buy") or 0,
                    )
                )

            enriched.append(
                {
                    key: row[key],
                    "kwh": (
                        round(row["kwh"], 1)
                        if row.get("kwh") is not None
                        else None
                    ),
                    "cons": (
                        round(row["cons"], 1)
                        if row.get("cons") is not None
                        else None
                    ),
                    "buy": (
                        round(row["buy"], 1)
                        if row.get("buy") is not None
                        else None
                    ),
                    "days": days,
                    "saved": saved,
                    "batt": (
                        round(row["batt"], 1)
                        if row.get("batt") is not None
                        else None
                    ),
                    "batt_days": row.get("batt_days") or 0,
                }
            )
        return enriched

    monthly = enrich(store.monthly(60), "month")
    yearly_savings: dict[str, int] = {}
    for month in monthly:
        if month.get("saved") is not None:
            year = month["month"][:4]
            yearly_savings[year] = (
                yearly_savings.get(year, 0) + month["saved"]
            )

    yearly = []
    for row in store.yearly():
        year = row["year"]
        yearly.append(
            {
                "year": year,
                "kwh": (
                    round(row["kwh"], 1)
                    if row.get("kwh") is not None
                    else None
                ),
                "cons": (
                    round(row["cons"], 1)
                    if row.get("cons") is not None
                    else None
                ),
                "buy": (
                    round(row["buy"], 1)
                    if row.get("buy") is not None
                    else None
                ),
                "days": row.get("days") or 0,
                "saved": yearly_savings.get(year),
            }
        )

    return {
        "currency": currency,
        "monthly": monthly,
        "yearly": yearly,
        "records": compute_records(store.daily_full(4000)),
    }
