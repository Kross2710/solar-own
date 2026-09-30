"""Báo cáo kỳ hoá đơn EVN đã chốt — logic THUẦN (không đụng store/config).

Báo cáo là một *view* tính lại được bất kỳ lúc nào từ các bảng vĩnh viễn
(`daily`, `curtailment`, `evn_bills`) — không lưu, không job rollover.
API chỉ trả SỐ; câu chữ song ngữ do frontend dựng qua t() (key report.*).

Quy ước kỳ: [cs, ce) — ce là ngày đầu kỳ SAU (exclusive). offset=1 = kỳ
hoàn chỉnh gần nhất, offset càng lớn càng lùi về quá khứ.

Định giá curtailment kỳ đã chốt: tariff.marginal(buy CỦA CHÍNH KỲ ĐÓ) —
cùng nguyên tắc bậc-biên với /api/curtailment (card live dùng trailing-30d
vì kỳ chưa chốt; ở đây buy thật của kỳ đã biết nên chính xác hơn).
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional

from providers.evn import EvnTariff


def cycle_bounds(today: date, start_day: int):
    """(cycle_start, days_in_cycle, days_elapsed, cycle_end) cho kỳ hoá đơn EVN.

    (Di dời nguyên văn từ server._cycle_bounds — server import alias lại để
    test/code cũ không đổi.)
    """
    sd = min(start_day, calendar.monthrange(today.year, today.month)[1])
    if today.day >= sd:
        cs = today.replace(day=sd)
    else:
        y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        cs = today.replace(year=y, month=m, day=min(start_day, calendar.monthrange(y, m)[1]))
    y2, m2 = (cs.year, cs.month + 1) if cs.month < 12 else (cs.year + 1, 1)
    ce = cs.replace(year=y2, month=m2, day=min(start_day, calendar.monthrange(y2, m2)[1]))
    return cs, max(1, (ce - cs).days), max(1, (today - cs).days + 1), ce


def closed_cycle_bounds(today: date, start_day: int, offset: int):
    """[cs, ce) của kỳ ĐÃ CHỐT thứ `offset` tính ngược (offset=1 = kỳ gần nhất).

    Bước lùi `cs − 1 ngày` luôn rơi vào kỳ liền trước bất kể clamp cuối tháng
    (bất biến cs <= d < ce đã được test trong test_money.py).
    """
    cs, _, _, _ = cycle_bounds(today, start_day)  # kỳ HIỆN TẠI (chưa chốt)
    ce = cs
    for _ in range(max(1, offset)):
        ce = cs
        cs, _, _, _ = cycle_bounds(cs - timedelta(days=1), start_day)
    return cs, ce


def _has_data(r: dict) -> bool:
    return r.get("kwh") is not None or r.get("cons") is not None or r.get("buy") is not None


def count_closed_cycles(rows: list, today: date, start_day: int, cap: int = 120) -> int:
    """Số kỳ đã chốt còn GIAO với dữ liệu (ce > ngày đầu tiên có số liệu)."""
    first = None
    for r in rows:
        if _has_data(r):
            d = r["day"]
            if first is None or d < first:
                first = d
    if first is None:
        return 0
    n = 0
    for off in range(1, cap + 1):
        _cs, ce = closed_cycle_bounds(today, start_day, off)
        if ce.isoformat() <= first:
            break
        n += 1
    return n


def _cycle_sums(rows: list, cs_iso: str, ce_iso: str) -> dict:
    """Tổng + coverage của một kỳ [cs, ce). Tổng dùng `or 0` (NULL lẻ tẻ = 0)."""
    cyc = [r for r in rows if cs_iso <= r["day"] < ce_iso]
    gen = sum((r.get("kwh") or 0) for r in cyc)
    cons = sum((r.get("cons") or 0) for r in cyc)
    buy = sum((r.get("buy") or 0) for r in cyc)
    gen_rows = [r for r in cyc if r.get("kwh") is not None]
    best = max(gen_rows, key=lambda r: r["kwh"], default=None)
    worst = min(gen_rows, key=lambda r: r["kwh"], default=None)
    return {
        "gen": gen, "cons": cons, "buy": buy,
        "gen_days": len(gen_rows),
        "cons_days": sum(1 for r in cyc if r.get("cons") is not None),
        "buy_days": sum(1 for r in cyc if r.get("buy") is not None),
        "data_days": sum(1 for r in cyc if _has_data(r)),
        "has_first_buy": any(r["day"] == cs_iso and r.get("buy") is not None for r in cyc),
        "best": best, "worst": worst,
    }


def _self_pct(cons: float, buy: float) -> Optional[float]:
    # cons=0 -> None (không chia); buy > cons (nhiễu đo) -> clamp 0
    if cons <= 0:
        return None
    return round(max(0.0, 1 - buy / cons) * 100, 1)


def _money_block(s: dict, tariff: EvnTariff) -> dict:
    # Thiếu hẳn cons hoặc buy trong kỳ -> None thay vì số vô nghĩa
    # (savings(0, buy) sẽ ra ÂM giả tạo).
    est_bill = round(tariff.cost(s["buy"])) if s["buy_days"] else None
    saved = round(tariff.savings(s["cons"], s["buy"])) if (s["cons_days"] and s["buy_days"]) else None
    return {"est_bill": est_bill, "saved": saved}


def compute_report(rows: list, curtail_rows: list, bills: list, tariff: EvnTariff,
                   today: date, start_day: int, offset: int) -> dict:
    """Báo cáo một kỳ đã chốt. Trả ready:false (out_of_range | no_data) khi không có gì."""
    offset = max(1, int(offset))
    available = count_closed_cycles(rows, today, start_day)
    cs, ce = closed_cycle_bounds(today, start_day, offset)
    cs_iso, ce_iso = cs.isoformat(), ce.isoformat()
    label = cs.strftime("%Y-%m")
    days = (ce - cs).days

    if offset > available:
        return {"ready": False, "reason": "out_of_range",
                "available": available, "offset": offset}

    s = _cycle_sums(rows, cs_iso, ce_iso)
    cycle_info = {"start": cs_iso, "end": ce_iso, "label": label, "days": days,
                  "days_with_data": s["data_days"],
                  # cùng tiêu chí est_reliable của _evn_bill_block: có ngày ĐẦU kỳ
                  # + phủ >= days-1 ngày buy -> mới dám so với hoá đơn thật
                  "complete": s["has_first_buy"] and s["buy_days"] >= days - 1}
    if s["data_days"] == 0:
        return {"ready": False, "reason": "no_data", "available": available,
                "offset": offset, "cycle": cycle_info}

    money = _money_block(s, tariff)

    # --- Hoá đơn EVN thật (bảng evn_bills, key 'YYYY-MM') ---------------------
    # label == tháng dương lịch của cs — đúng vì cycle_start_day=1; nếu sau này
    # đổi ngày chốt giữa tháng thì phải quyết định lại phép map kỳ->bill.
    evn_bill = None
    b = next((x for x in bills if x.get("cycle") == label and x.get("amount") is not None), None)
    if b:
        diff_pct = None
        if cycle_info["complete"] and money["est_bill"]:
            diff_pct = round((b["amount"] - money["est_bill"]) / money["est_bill"] * 100, 1)
        evn_bill = {"amount": round(b["amount"]),
                    "kwh": round(b["kwh"], 1) if b.get("kwh") is not None else None,
                    "paid_date": b.get("paid_date"),
                    "diff_pct": diff_pct, "reliable": cycle_info["complete"]}

    # --- Curtailment: không có row nào trong kỳ -> null (khác với lost=0) -----
    curtail = None
    crows = [r for r in curtail_rows if cs_iso <= r["day"] < ce_iso]
    if crows:
        lost = sum((r.get("lost") or 0) for r in crows)
        marginal = round(tariff.marginal(s["buy"]))
        curtail = {"lost_kwh": round(lost, 1),
                   "days": sum(1 for r in crows if (r.get("lost") or 0) > 0),
                   "marginal": marginal, "value": round(lost * marginal)}

    # --- Kỳ liền trước (offset+1): chỉ kèm khi có dữ liệu ---------------------
    prev = None
    pcs, pce = closed_cycle_bounds(today, start_day, offset + 1)
    p = _cycle_sums(rows, pcs.isoformat(), pce.isoformat())
    if p["data_days"] > 0:
        pmoney = _money_block(p, tariff)

        def _pct(cur, old):
            return round((cur - old) / old * 100) if old > 0 else None

        prev = {"gen_kwh": round(p["gen"], 1), "cons_kwh": round(p["cons"], 1),
                "buy_kwh": round(p["buy"], 1), "saved": pmoney["saved"],
                "gen_delta_pct": _pct(s["gen"], p["gen"]),
                "cons_delta_pct": _pct(s["cons"], p["cons"]),
                "buy_delta_pct": _pct(s["buy"], p["buy"]),
                "saved_delta": (money["saved"] - pmoney["saved"])
                               if (money["saved"] is not None and pmoney["saved"] is not None) else None}

    return {
        "ready": True, "offset": offset, "available": available,
        "cycle": cycle_info,
        "energy": {"gen_kwh": round(s["gen"], 1), "cons_kwh": round(s["cons"], 1),
                   "buy_kwh": round(s["buy"], 1),
                   "self_pct": _self_pct(s["cons"], s["buy"])},
        "money": money,
        "evn_bill": evn_bill,
        "curtail": curtail,
        "best_day": {"day": s["best"]["day"], "kwh": round(s["best"]["kwh"], 1)} if s["best"] else None,
        "worst_day": {"day": s["worst"]["day"], "kwh": round(s["worst"]["kwh"], 1)} if s["worst"] else None,
        "prev": prev,
    }
