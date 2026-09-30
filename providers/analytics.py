"""Phân tích nâng cao từ đường cong 5 phút trong ngày.

Hiện có: ước tính ĐIỆN NẮNG BỊ BỎ PHÍ (curtailment) — khi pin đầy lúc trưa,
inverter ép giảm công suất PV xuống ~bằng tải (hệ không bán lưới), nên phần nắng
lẽ ra phát được bị vứt đi. Ta KHÔNG có bức xạ 5 phút của quá khứ, nên ước lượng
"tiềm năng" bằng đường bao nửa-sin khớp với phần buổi sáng CHƯA bị cắt (SOC chưa
đầy). Phần thiếu hụt trong lúc SOC≈đầy = lượng bị bỏ phí. Có nhãn "ước tính".
"""
from __future__ import annotations

import math
from typing import Optional


def _mins(t: str) -> Optional[int]:
    """'HH:MM' -> phút trong ngày."""
    try:
        h, m = str(t).split(":")[:2]
        return int(h) * 60 + int(m)
    except Exception:
        return None


def estimate_curtailment(points: list, reserve_pct: float = 20.0,
                         capacity_kw: Optional[float] = None) -> dict:
    """points: [{t,'pv','load','grid','soc',...}] (5 phút/điểm, W & %).

    Trả {lost_kwh, actual_kwh, potential_kwh, full_at, samples}.
    """
    rows = []
    for p in points or []:
        mn = _mins(p.get("t"))
        if mn is None:
            continue
        pv = p.get("pv")
        rows.append({
            "m": mn,
            "pv": float(pv) if pv is not None else 0.0,
            "soc": (None if p.get("soc") is None else float(p["soc"])),
            "grid": (None if p.get("grid") is None else float(p["grid"])),
        })
    none = {"lost_kwh": 0.0, "actual_kwh": 0.0, "potential_kwh": 0.0,
            "full_at": None, "samples": len(rows)}
    if len(rows) < 6:
        return none

    rows.sort(key=lambda r: r["m"])
    dt_h = 5.0 / 60.0  # mỗi điểm 5 phút
    actual_kwh = round(sum(r["pv"] for r in rows) * dt_h / 1000.0, 1)

    # Đỉnh PV THỰC đo được trong ngày (mốc thực tế, không ngoại suy)
    ppeak = max(r["pv"] for r in rows)
    if capacity_kw:
        ppeak = min(ppeak, capacity_kw * 1000.0)
    if ppeak < 800:  # ngày gần như không nắng -> không xét curtailment
        return {**none, "actual_kwh": actual_kwh, "potential_kwh": actual_kwh}

    # Cửa sổ ban ngày HIỆU DỤNG: cắt đuôi tù mù (PV nhỏ) để nửa-sin không quá rộng.
    thr = max(400.0, 0.12 * ppeak)
    day = [r for r in rows if r["pv"] >= thr]
    if len(day) < 3:
        return {**none, "actual_kwh": actual_kwh, "potential_kwh": actual_kwh}
    t0, t1 = day[0]["m"], day[-1]["m"]
    span = max(1, t1 - t0)

    def sinf(m):  # đường bao nửa-sin trong cửa sổ hiệu dụng: 0 ở 2 biên, 1 ở giữa
        x = (m - t0) / span
        if x <= 0 or x >= 1:
            return 0.0
        return math.sin(math.pi * x)

    # Tổn thất: chỉ trong lúc SOC≈đầy (>=95) và KHÔNG bán mạnh ra lưới.
    potential_wh = lost_wh = 0.0
    full_at = None
    for r in rows:
        pot = ppeak * sinf(r["m"])  # đường bao nửa-sin, đỉnh = PV thực đo được
        potential_wh += max(pot, r["pv"])
        soc_full = r["soc"] is not None and r["soc"] >= 95
        not_exporting = r["grid"] is None or r["grid"] >= -200  # grid<0 = bán (không phí)
        if soc_full and not_exporting and pot > r["pv"]:
            lost_wh += (pot - r["pv"])
        if full_at is None and r["soc"] is not None and r["soc"] >= 98:
            full_at = _fmt(r["m"])

    return {
        "lost_kwh": round(lost_wh * dt_h / 1000.0, 1),
        "actual_kwh": actual_kwh,
        "potential_kwh": round(potential_wh * dt_h / 1000.0, 1),
        "full_at": full_at,
        "samples": len(rows),
    }


def _fmt(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"
