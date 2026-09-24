"""Nguồn dữ liệu GIẢ LẬP — để xem giao diện chạy ngay mà chưa cần SEMS/inverter.

Tạo một đường cong mặt trời theo giờ trong ngày (6h–18h) cộng nhiễu nhẹ, để
dashboard trông sống động và giống thật.
"""
from __future__ import annotations

import math
import random
from datetime import datetime

from .base import Provider, Metrics, VN_TZ


class MockProvider(Provider):
    name = "mock"

    def __init__(self, station_name: str = "Nhà mình (giả lập)", capacity_kw: float = 5.0):
        self.station_name = station_name
        self.capacity_kw = capacity_kw
        self._total = 5421.0  # tổng sản lượng tích luỹ khởi điểm (kWh)
        self._batt_chg = 1364.0  # nạp pin lũy kế (kWh) — cho trang Sức khoẻ pin (dev)
        self._batt_dis = 1356.0  # xả pin lũy kế (kWh)

    async def get_metrics(self) -> Metrics:
        now = datetime.now(VN_TZ)
        hour = now.hour + now.minute / 60.0

        # Đường cong mặt trời: 0 trước 6h và sau 18h, đỉnh giữa trưa.
        sun = max(0.0, math.sin((hour - 6.0) / 12.0 * math.pi)) if 6 <= hour <= 18 else 0.0
        sun *= 1.0 + random.uniform(-0.06, 0.06)  # mây/nhiễu
        pv = max(0.0, self.capacity_kw * 1000.0 * sun)

        # Tải nhà: nền ~350W + sinh hoạt ban ngày
        base_load = 350.0
        active = 0.4 + 0.6 * random.random()
        load = base_load + 700.0 * active * (1.0 if 6 < hour < 23 else 0.35)

        grid = load - pv  # >0 mua, <0 bán
        today = self.capacity_kw * 4.2 * sun  # ước lượng sản lượng hôm nay
        # Tiêu thụ + mua lưới hôm nay (giả lập, tự nhất quán: từ PV và pin = cons - buy = PV tự dùng)
        today_buy = 6.0 + today * 0.15         # nền ~6 kWh lấy từ lưới + thiếu hụt ban ngày
        today_cons = today + 6.0               # = PV tự dùng (0.85·today) + mua lưới
        self._total += pv / 1000.0 / 720.0     # cộng dồn nhẹ theo mỗi lần gọi
        # Pin giả lập: SOC theo đường mặt trời (sạc ngày, xả đêm), throughput cộng dồn nhẹ.
        soc = round(35.0 + 60.0 * sun + 5.0 * random.random(), 0)
        batt_w = round((pv - load) * 0.5) if sun > 0.05 else round(-load * 0.6)
        self._batt_chg += max(0.0, pv - load) / 1000.0 / 720.0
        self._batt_dis += max(0.0, load - pv) / 1000.0 / 720.0

        return Metrics(
            source="mock",
            status="online",
            station_name=self.station_name,
            pv_power_w=round(pv),
            load_power_w=round(load),
            grid_power_w=round(grid),
            battery_power_w=batt_w,
            battery_soc=soc,
            today_energy_kwh=round(today, 1),
            total_energy_kwh=round(self._total, 1),
            today_income=round(today * 2000),   # ~2.000đ/kWh
            currency="VND",
            capacity_kw=self.capacity_kw,
            self_use_rate=0.6,
            today_buy_kwh=round(today_buy, 1),
            today_sell_kwh=round(today * 0.15, 1),
            today_consumption_kwh=round(today_cons, 1),
            month_energy_kwh=round(self.capacity_kw * 90, 1),
            month_income=round(self.capacity_kw * 90 * 2000),
            total_income=round(self._total * 2000),
            battery_capacity_kwh=20.0,
            lat=21.03,
            lon=105.85,
        )
