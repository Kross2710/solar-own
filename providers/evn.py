"""Biểu giá điện sinh hoạt EVN bậc thang (đã đối chiếu hoá đơn thực tế).

Kiểm chứng với hoá đơn KH Đàm Thanh Lan kỳ 1 tháng 5/2026:
  237 kWh -> 594.676đ (khớp 100%);  1.118 kWh -> 3.843.482đ (≈ "không solar" 3.844.230đ).

Bậc (đ/kWh, CHƯA VAT): 1:0-50=1984, 2:51-100=2050, 3:101-200=2380,
                       4:201-300=2998, 5:301-400=3350, 6:>400=3460.  + 8% VAT.
Bậc thang reset theo THÁNG nên mọi tính toán tiền phải theo kỳ/tháng.
"""
from __future__ import annotations

from typing import Optional
from datetime import date, timedelta
import math

# (ngưỡng tích luỹ kWh hoặc None = bậc cuối, giá đ/kWh chưa VAT)
DEFAULT_TIERS = [(50, 1984.0), (100, 2050.0), (200, 2380.0),
                 (300, 2998.0), (400, 3350.0), (None, 3460.0)]
DEFAULT_VAT = 0.08
NOVEMBER_2026_TIERS = [(100, 1901.0), (200, 2289.0), (400, 2894.0),
                       (700, 3456.0), (None, 3844.0)]


class EvnTariff:
    def __init__(self, tiers: Optional[list] = None, vat: float = DEFAULT_VAT):
        self.tiers = [(t[0], float(t[1])) for t in (tiers or DEFAULT_TIERS)]
        self.vat = float(vat)
        if not 0 <= self.vat <= 1:
            raise ValueError("VAT must be between 0 and 1")
        previous = 0
        for index, (upto, price) in enumerate(self.tiers):
            if not math.isfinite(price) or price <= 0 or (upto is None and index != len(self.tiers) - 1):
                raise ValueError("Invalid tariff tier")
            if upto is not None:
                if not math.isfinite(float(upto)) or float(upto) <= previous:
                    raise ValueError("Tariff bounds must increase")
                previous = float(upto)
        if self.tiers[-1][0] is not None:
            raise ValueError("Last tariff tier must be open-ended")
        self.effective_from = "2025-05-10"
        self.label = "EVN residential · 6 tiers" if self.tiers == DEFAULT_TIERS else "Custom residential tariff"
        self.schedule = []
        if self.tiers == DEFAULT_TIERS:
            self.schedule = [("0001-01-01", self.tiers, self.vat, self.label),
                             ("2026-11-01", NOVEMBER_2026_TIERS, self.vat, "EVN residential · 5 tiers")]

    @classmethod
    def from_config(cls, cfg: Optional[dict]) -> "EvnTariff":
        cfg = cfg or {}
        tiers = None
        if cfg.get("tiers"):
            tiers = []
            for t in cfg["tiers"]:
                if isinstance(t, dict):
                    tiers.append((t.get("upto"), t.get("price")))
                else:
                    tiers.append((t[0], t[1]))
        result = cls(tiers=tiers, vat=cfg.get("vat", DEFAULT_VAT))
        if cfg.get("schedules"):
            result.schedule = []
            for item in cfg["schedules"]:
                start = date.fromisoformat(item["effective_from"]).isoformat()
                snapshot = cls.from_config({"tiers": item["tiers"], "vat": item.get("vat", result.vat)})
                result.schedule.append((start, snapshot.tiers, snapshot.vat, item.get("label", "Custom tariff")))
            result.schedule.sort(key=lambda item: item[0])
            if len({item[0] for item in result.schedule}) != len(result.schedule):
                raise ValueError("Duplicate tariff effective date")
        return result

    def at(self, day: date | str) -> "EvnTariff":
        """Resolve a snapshot; timeless cost()/marginal() remain usable for custom tariffs."""
        iso = day.isoformat() if isinstance(day, date) else day
        candidates = [entry for entry in self.schedule if entry[0] <= iso]
        if not candidates:
            if self.schedule:
                raise ValueError("No tariff configured for this date")
            return self
        start, tiers, vat, label = candidates[-1]
        snapshot = EvnTariff(tiers, vat)
        snapshot.schedule = []
        snapshot.effective_from = "2025-05-10" if start == "0001-01-01" else start
        snapshot.label = label
        return snapshot

    def period_cost(self, kwh: float, start: date, end: date) -> float:
        """Estimate a billing period [start,end), prorating quotas at tariff changes.

        Without an EVN change-date meter read, volume is allocated by calendar days.
        This is explicitly an estimate, never a replacement for the actual EVN bill.
        """
        if end <= start:
            raise ValueError("Billing period must have positive duration")
        cuts = [start] + [date.fromisoformat(entry[0]) for entry in self.schedule
                          if start.isoformat() < entry[0] < end.isoformat()] + [end]
        days = (end - start).days
        return sum(self.at(a).cost(kwh) * ((b - a).days / days)
                   for a, b in zip(cuts, cuts[1:]))

    def period_savings(self, consumption: float, buy: float, start: date, end: date) -> float:
        return self.period_cost(consumption, start, end) - self.period_cost(buy, start, end)

    def period_info(self, start: date, end: date) -> dict:
        snapshot = self.at(end - timedelta(days=1))
        mixed = any(start.isoformat() < entry[0] < end.isoformat() for entry in self.schedule)
        return {"label": snapshot.label, "effective_from": snapshot.effective_from,
                "vat": snapshot.vat, "includes_vat": True, "mixed": mixed,
                "allocation": "estimated_by_days" if mixed else "single_tariff"}


    def cost(self, kwh: Optional[float], with_vat: bool = True) -> float:
        """Tiền điện cho `kwh` tiêu thụ trong 1 kỳ (bậc thang). Mặc định gồm VAT."""
        if not kwh or kwh <= 0:
            return 0.0
        total = 0.0
        lower = 0.0
        for upto, price in self.tiers:
            upper = float(upto) if upto is not None else float(kwh)
            seg = min(kwh, upper) - lower
            if seg > 0:
                total += seg * price
            lower = upper
            if kwh <= upper:
                break
        return total * (1 + self.vat) if with_vat else total

    def marginal(self, level_kwh: float, with_vat: bool = True) -> float:
        """Giá của kWh KẾ TIẾP khi đã tiêu thụ `level_kwh` trong kỳ (giá biên)."""
        for upto, price in self.tiers:
            if upto is None or level_kwh < float(upto):
                return price * (1 + self.vat) if with_vat else price
        p = self.tiers[-1][1]
        return p * (1 + self.vat) if with_vat else p

    def savings(self, consumption_kwh: float, grid_buy_kwh: float) -> float:
        """Tiết kiệm = tiền nếu mua TẤT CẢ tiêu thụ − tiền thực mua (cả hai bậc thang+VAT)."""
        return self.cost(consumption_kwh) - self.cost(grid_buy_kwh)
