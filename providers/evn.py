"""Biểu giá điện sinh hoạt EVN bậc thang (đã đối chiếu hoá đơn thực tế).

Kiểm chứng với hoá đơn KH Đàm Thanh Lan kỳ 1 tháng 5/2026:
  237 kWh -> 594.676đ (khớp 100%);  1.118 kWh -> 3.843.482đ (≈ "không solar" 3.844.230đ).

Bậc (đ/kWh, CHƯA VAT): 1:0-50=1984, 2:51-100=2050, 3:101-200=2380,
                       4:201-300=2998, 5:301-400=3350, 6:>400=3460.  + 8% VAT.
Bậc thang reset theo THÁNG nên mọi tính toán tiền phải theo kỳ/tháng.
"""
from __future__ import annotations

from typing import Optional

# (ngưỡng tích luỹ kWh hoặc None = bậc cuối, giá đ/kWh chưa VAT)
DEFAULT_TIERS = [(50, 1984.0), (100, 2050.0), (200, 2380.0),
                 (300, 2998.0), (400, 3350.0), (None, 3460.0)]
DEFAULT_VAT = 0.08


class EvnTariff:
    def __init__(self, tiers: Optional[list] = None, vat: float = DEFAULT_VAT):
        self.tiers = [(t[0], float(t[1])) for t in (tiers or DEFAULT_TIERS)]
        self.vat = float(vat)

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
        return cls(tiers=tiers, vat=cfg.get("vat", DEFAULT_VAT))

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
