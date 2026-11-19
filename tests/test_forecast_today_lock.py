"""Số dự báo hôm nay phải ổn định cả ngày: tính một lần, giữ nguyên dù thời tiết
hôm nay đổi (lần refresh 2 lần/ngày), và ngày mai vẫn tính lại."""
from datetime import date, timedelta

from providers.forecast import SolarForecaster


def _rows(n_days, base_rad=20.0, base_kwh=30.0):
    today = date.today()
    rows = []
    for i in range(n_days):
        d = (today - timedelta(days=n_days - i - 1)).isoformat()
        rows.append({"day": d, "kwh": base_kwh + (i % 4), "rad": base_rad + (i % 3)})
    return rows


class TestTodayLock:
    def setup_method(self, method):
        self.fc = SolarForecaster()
        assert self.fc.fit(_rows(40), date.today().isoformat())

    def test_same_day_returns_cached_value(self):
        day = "2099-03-04"
        w = {day: {"rad": 20.0}}
        first = self.fc.today_yield_locked(day, w)
        second = self.fc.today_yield_locked(day, w)
        assert first is not None and first == second

    def test_weather_change_does_not_move_locked_number(self):
        # Key behaviour: today's number must NOT move when the day's weather changes
        # (i.e. across the twice-daily weather refresh).
        day = "2099-03-04"
        first = self.fc.today_yield_locked(day, {day: {"rad": 20.0}})
        second = self.fc.today_yield_locked(day, {day: {"rad": 4.0}})  # very different
        assert first is not None
        assert first == second, f"locked number moved: {first} -> {second}"

    def test_new_day_is_not_locked(self):
        v1 = self.fc.today_yield_locked("2099-03-04", {"2099-03-04": {"rad": 20.0}})
        v2 = self.fc.today_yield_locked("2099-03-05", {"2099-03-05": {"rad": 20.0}})
        assert v1 is not None and v2 is not None
        assert self.fc.today_lock == "2099-03-05"

    def test_missing_weather_is_not_locked(self):
        # No weather for the day -> None, and nothing cached (retry next time).
        assert self.fc.today_yield_locked("2099-03-04", {}) is None
        assert self.fc.today_lock is None

    def test_locked_value_is_rounded_to_one_decimal(self):
        # Must match predict_days rounding so today's API value isn't more precise.
        day = "2099-03-04"
        val = self.fc.today_yield_locked(day, {day: {"rad": 20.0}})
        assert val is not None
        assert val == round(val, 1)
