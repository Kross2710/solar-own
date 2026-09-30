"""EVN tiered-tariff money calculations for the Money tab."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from providers.evn import EvnTariff

if TYPE_CHECKING:
    from backend.runtime import AppRuntime


Row = dict[str, Any]


def cycle_bounds(today: date, start_day: int) -> tuple[date, int, int, date]:
    """Return (cycle_start, days_in_cycle, days_elapsed, cycle_end) of the EVN billing cycle.

    cycle_end is exclusive. start_day is clamped to the length of short months.
    """
    start = min(start_day, calendar.monthrange(today.year, today.month)[1])
    if today.day >= start:
        cycle_start = today.replace(day=start)
    else:
        year, month = (
            (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        )
        cycle_start = today.replace(
            year=year,
            month=month,
            day=min(start_day, calendar.monthrange(year, month)[1]),
        )

    end_year, end_month = (
        (cycle_start.year, cycle_start.month + 1)
        if cycle_start.month < 12
        else (cycle_start.year + 1, 1)
    )
    cycle_end = cycle_start.replace(
        year=end_year,
        month=end_month,
        day=min(start_day, calendar.monthrange(end_year, end_month)[1]),
    )
    return (
        cycle_start,
        max(1, (cycle_end - cycle_start).days),
        max(1, (today - cycle_start).days + 1),
        cycle_end,
    )


def tier_ladder(tariff: EvnTariff, level_kwh: float) -> dict[str, Any]:
    """Current tier for the kWh bought this cycle, plus bounds/prices (VAT incl.) for the UI ladder."""
    tiers = tariff.tiers
    vat = tariff.vat
    level = max(0.0, level_kwh or 0.0)

    current = len(tiers) - 1
    for index, (upto, _price) in enumerate(tiers):
        if upto is None or level < float(upto):
            current = index
            break

    current_price = tiers[current][1] * (1 + vat)
    current_upto = tiers[current][0]
    to_next = next_jump = None
    if current_upto is not None and current + 1 < len(tiers):
        to_next = round(float(current_upto) - level, 1)
        next_jump = round(tiers[current + 1][1] * (1 + vat) - current_price)

    return {
        "index": current,
        "count": len(tiers),
        "level_kwh": round(level, 1),
        "cur_price": round(current_price),
        "to_next_kwh": to_next,
        "next_jump": next_jump,
        "bounds": [tier[0] for tier in tiers],
        "prices": [round(tier[1] * (1 + vat)) for tier in tiers],
    }


def project_cycle_spend(
    cycle_buy: float,
    cycle_cons: float,
    days_in_cycle: int,
    days_elapsed: int,
) -> tuple[float, float, float | None, float | None, str]:
    """Project end-of-cycle (buy, cons, bill_lo, bill_hi, method) by scaling the running totals.

    Only the "flat" method exists until the load forecaster is ported; it has no
    confidence band, so bill_lo/bill_hi are None.
    """
    factor = days_in_cycle / days_elapsed
    return cycle_buy * factor, cycle_cons * factor, None, None, "flat"


def monthly_savings(
    rows: list[Row],
    tariff: EvnTariff,
) -> tuple[dict[str, dict[str, Any]], float]:
    """Group cons/buy per calendar month and sum the savings.

    Tiers reset monthly, so savings are computed per month, never on the grand total.
    """
    months: dict[str, dict[str, Any]] = {}
    for row in rows:
        month = months.setdefault(
            row["day"][:7], {"cons": 0.0, "buy": 0.0, "has": False}
        )
        if row.get("cons") is not None or row.get("buy") is not None:
            month["cons"] += row.get("cons") or 0
            month["buy"] += row.get("buy") or 0
            month["has"] = True

    total_saved = sum(
        tariff.savings(month["cons"], month["buy"])
        for month in months.values()
        if month["has"]
    )
    return months, total_saved


def payback_block(
    rows: list[Row],
    today: date,
    tariff: EvnTariff,
    months: dict[str, dict[str, Any]],
    total_saved: float,
    without_solar_proj: float,
    bill_proj: float,
    invest_total: float,
) -> dict[str, Any] | None:
    """Payback progress, or None when no investment amount is configured.

    The pace is the average saving of finished months (the current month is
    partial); without any finished month it falls back to this cycle's projection,
    then to total / months.
    """
    if invest_total <= 0:
        return None

    recovered = total_saved
    remaining = max(0.0, invest_total - recovered)
    current_month = today.strftime("%Y-%m")
    done_savings = [
        tariff.savings(month["cons"], month["buy"])
        for key, month in months.items()
        if month["has"] and key != current_month
    ]
    data_months = sum(1 for month in months.values() if month["has"])

    if done_savings:
        avg_month = sum(done_savings) / len(done_savings)
    elif without_solar_proj - bill_proj > 0:
        avg_month = without_solar_proj - bill_proj
    else:
        avg_month = total_saved / data_months if data_months else 0.0

    months_left = eta = None
    if remaining <= 0:
        months_left = 0.0
    elif avg_month > 0:
        months_left = remaining / avg_month
        eta = (today + timedelta(days=months_left * 30.44)).isoformat()

    return {
        "invest": round(invest_total),
        "recovered": round(recovered),
        "remaining": round(remaining),
        "pct": round(recovered / invest_total * 100, 1),
        "avg_month": round(avg_month),
        "months_left": None if months_left is None else round(months_left, 1),
        "eta": eta,
        "commissioned": rows[0]["day"] if rows else None,
        "data_months": data_months,
        # Less than a full year (incl. rainy season) -> the estimate is optimistic.
        "low_confidence": data_months < 12,
        "done": remaining <= 0,
    }


def compute_money(
    rows: list[Row],
    tariff: EvnTariff,
    start_day: int,
    today: date,
    currency: str = "VND",
    invest_total: float = 0.0,
) -> dict[str, Any]:
    """Savings today / this cycle / all-time, projected EVN bill, tier ladder and payback."""
    cycle_start, days_in_cycle, days_elapsed, cycle_end = cycle_bounds(today, start_day)
    cycle_start_iso, today_iso = cycle_start.isoformat(), today.isoformat()
    cycle_rows = [row for row in rows if cycle_start_iso <= row["day"] <= today_iso]
    cycle_buy = sum(row.get("buy") or 0 for row in cycle_rows)
    cycle_cons = sum(row.get("cons") or 0 for row in cycle_rows)

    proj_buy, proj_cons, bill_lo, bill_hi, proj_method = project_cycle_spend(
        cycle_buy, cycle_cons, days_in_cycle, days_elapsed
    )
    bill_now, bill_proj = tariff.cost(cycle_buy), tariff.cost(proj_buy)
    without_solar_now = tariff.cost(cycle_cons)
    without_solar_proj = tariff.cost(proj_cons)
    marginal_cons = tariff.marginal(cycle_cons or proj_cons or 1)
    marginal_buy = tariff.marginal(cycle_buy or proj_buy or 1)

    today_row = next((row for row in rows if row["day"] == today_iso), None)
    today_saved = today_selfuse = None
    if today_row and today_row.get("cons") is not None:
        selfuse = max(0.0, (today_row.get("cons") or 0) - (today_row.get("buy") or 0))
        today_selfuse = round(selfuse, 1)
        today_saved = round(selfuse * marginal_cons)

    months, total_saved = monthly_savings(rows, tariff)

    # Previous cycle cut at the same number of elapsed days, so day N is compared with day N.
    prev_start, _, _, prev_end = cycle_bounds(cycle_start - timedelta(days=1), start_day)
    prev_cut = prev_start + timedelta(days=days_elapsed - 1)
    if prev_cut >= prev_end:
        prev_cut = prev_end - timedelta(days=1)
    prev_start_iso, prev_cut_iso = prev_start.isoformat(), prev_cut.isoformat()
    prev_rows = [row for row in rows if prev_start_iso <= row["day"] <= prev_cut_iso]
    prev_buy = sum(row.get("buy") or 0 for row in prev_rows)
    prev_bill = tariff.cost(prev_buy)

    return {
        "currency": currency,
        "marginal_cons": round(marginal_cons),
        "marginal_buy": round(marginal_buy),
        "tier": tier_ladder(tariff, cycle_buy),
        "prev_cycle": {
            "start": prev_start_iso,
            "days": days_elapsed,
            "has": any(row.get("buy") is not None for row in prev_rows),
            "buy_kwh": round(prev_buy, 1),
            "bill": round(prev_bill),
            "buy_delta_pct": (
                round((cycle_buy - prev_buy) / prev_buy * 100) if prev_buy else None
            ),
            "bill_delta": round(bill_now - prev_bill),
        },
        "today": {"saved": today_saved, "selfuse_kwh": today_selfuse},
        "cycle": {
            "start": cycle_start_iso,
            "end": cycle_end.isoformat(),
            "days_elapsed": days_elapsed,
            "days_in_cycle": days_in_cycle,
            "buy_kwh": round(cycle_buy, 1),
            "cons_kwh": round(cycle_cons, 1),
            "bill_now": round(bill_now),
            "saved_now": round(without_solar_now - bill_now),
            "proj_buy_kwh": round(proj_buy),
            "proj_cons_kwh": round(proj_cons),
            "bill_proj": round(bill_proj),
            "without_solar_proj": round(without_solar_proj),
            "saved_proj": round(without_solar_proj - bill_proj),
            "bill_proj_lo": None if bill_lo is None else round(bill_lo),
            "bill_proj_hi": None if bill_hi is None else round(bill_hi),
            "proj_method": proj_method,
        },
        "total": {
            "saved": round(total_saved),
            "months": sum(1 for month in months.values() if month["has"]),
        },
        "payback": payback_block(
            rows,
            today,
            tariff,
            months,
            total_saved,
            without_solar_proj,
            bill_proj,
            invest_total,
        ),
    }


def evn_bill_history(
    bills: list[Row],
    today: date,
    limit: int = 13,
) -> list[dict[str, Any]]:
    """Real EVN bills of the latest closed cycles, oldest first.

    13 cycles by default so the latest bill can be compared with the same month last year.
    """
    current_cycle = today.strftime("%Y-%m")
    closed = [
        {"cycle": bill["cycle"], "amount": round(bill["amount"])}
        for bill in bills
        if bill["cycle"] < current_cycle and bill.get("amount") is not None
    ]
    return closed[-limit:]


def evn_bill_block(
    bills: list[Row],
    rows: list[Row],
    tariff: EvnTariff,
    today: date,
) -> dict[str, Any] | None:
    """Real EVN bill of the latest closed cycle, compared with the dashboard estimate.

    est_reliable is False when the cycle misses its first day or more than one day
    of data (e.g. the commissioning month); the UI then hides the diff badge.
    """
    current_cycle = today.strftime("%Y-%m")
    closed = [
        bill
        for bill in bills
        if bill["cycle"] < current_cycle and bill.get("amount") is not None
    ]
    if not closed:
        return None

    bill = closed[-1]
    cycle = bill["cycle"]
    month_rows = [row for row in rows if row["day"][:7] == cycle]
    buy_days = [row for row in month_rows if row.get("buy") is not None]
    cycle_buy = sum(row.get("buy") or 0 for row in buy_days)
    days_in_month = calendar.monthrange(int(cycle[:4]), int(cycle[5:7]))[1]
    has_first_day = any(
        row["day"] == f"{cycle}-01" and row.get("buy") is not None
        for row in month_rows
    )
    est_reliable = has_first_day and len(buy_days) >= days_in_month - 1
    est_amount = tariff.cost(cycle_buy) if buy_days else None

    diff_pct = None
    if est_reliable and est_amount and bill.get("amount"):
        diff_pct = round((bill["amount"] - est_amount) / est_amount * 100, 1)

    return {
        "cycle": cycle,
        "amount": round(bill["amount"]),
        "kwh": round(bill["kwh"], 1) if bill.get("kwh") is not None else None,
        "paid_date": bill.get("paid_date"),
        "est_amount": round(est_amount) if est_amount is not None else None,
        "diff_pct": diff_pct,
        "est_reliable": est_reliable,
    }


def build_money(runtime: "AppRuntime", today: date) -> dict[str, Any]:
    """The /api/money payload: compute_money plus the real EVN bill blocks."""
    evn_config = runtime.config.get("evn") or {}
    investment = runtime.config.get("investment") or {}
    rows = runtime.store.daily_full(400)

    result = compute_money(
        rows,
        runtime.tariff,
        int(evn_config.get("cycle_start_day", 1)),
        today,
        currency=runtime.config.get("currency") or "VND",
        invest_total=float(investment.get("total_vnd") or 0),
    )
    try:
        bills = runtime.store.evn_bills_all()
    except Exception:
        bills = []
    evn_bill = evn_bill_block(bills, rows, runtime.tariff, today)
    if evn_bill:
        result["evn_bill"] = evn_bill
    result["evn_history"] = evn_bill_history(bills, today)
    try:
        result["solar_start"] = runtime.store.first_generation_day()
    except Exception:
        result["solar_start"] = rows[0]["day"] if rows else None
    return result
