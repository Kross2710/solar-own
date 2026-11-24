"""Phục hồi mốc công tơ (meter_baseline) bị thiếu khi thiết bị khởi động NỬA NGÀY.

Bug: lần đọc đầu trong ngày thiếu một chiều -> `meter_baseline` ghi mốc NULL cho
chiều đó và KHÔNG bao giờ lấp khi công tơ có số lại -> mua/bán hôm nay của chiều
đó luôn None. Chỉ sửa `providers/history.py`: lấp mốc NULL khi chiều đó có số, dùng
upsert COALESCE để không ghi đè mốc chiều đã có, đường đọc đủ mốc vẫn nhẹ.

Ngày cố định (không phụ giờ hệ thống) để mọi lần chạy đều tái hiện được bug.
"""
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest import mock

from providers.history import HistoryStore


class MeterBaselineRecoveryTests(TestCase):
    DAY = "2026-11-23"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "history.db"
        self.store = HistoryStore(self.path)

    def _set_buy(self, value):
        """Đặt daily.buy (mốc seed khi import lần đầu) cho ngày thử nghiệm."""
        con = sqlite3.connect(self.path)
        try:
            con.execute(
                "INSERT OR REPLACE INTO daily(day, buy) VALUES (?, ?)",
                (self.DAY, value),
            )
            con.commit()
        finally:
            con.close()

    def _baseline(self):
        """Mốc imp0/exp0 đang lưu trong meter_baseline (hoặc None nếu chưa có dòng)."""
        con = sqlite3.connect(self.path)
        try:
            row = con.execute(
                "SELECT imp0, exp0 FROM meter_baseline WHERE day=?", (self.DAY,)
            ).fetchone()
            return None if row is None else (row[0], row[1])
        finally:
            con.close()

    def test_export_present_first_then_import_recovers_seed_and_grows(self):
        # Lần đọc đầu chỉ có BÁN -> mốc imp0 NULL, exp0 = 10.
        self._set_buy(5.0)
        self.assertEqual(self.store.meter_today(self.DAY, None, 10.0), (None, 0.0))
        self.assertEqual(self._baseline(), (None, 10.0))

        # Import có số lại: seed = imp - daily.buy -> imp0 = 15 - 5 = 10.
        # Mua hôm nay = 15 - 10 = 5 (= daily.buy), bán = 20 - 10 = 10 (giữ mốc exp0).
        self.assertEqual(self.store.meter_today(self.DAY, 15.0, 20.0), (5.0, 10.0))
        self.assertEqual(self._baseline(), (10.0, 10.0))

        # Import tiếp tục tăng: delta tính trên mốc imp0 đã lưu (10), không làm mới mốc.
        self.assertEqual(self.store.meter_today(self.DAY, 25.0, 30.0), (15.0, 20.0))
        self.assertEqual(self._baseline(), (10.0, 10.0))

    def test_import_present_first_then_export_recovers_zero_and_grows(self):
        # Lần đọc đầu chỉ có MUA (buy=0) -> imp0 = 5, exp0 NULL.
        self._set_buy(0.0)
        self.assertEqual(self.store.meter_today(self.DAY, 5.0, None), (0.0, None))
        self.assertEqual(self._baseline(), (5.0, None))

        # Bán có số lại: exp0 = 3 -> bán = 3 - 3 = 0 (báo zero). Mua = 8 - 5 = 3 (giữ imp0).
        self.assertEqual(self.store.meter_today(self.DAY, 8.0, 3.0), (3.0, 0.0))
        self.assertEqual(self._baseline(), (5.0, 3.0))

        # Bán tiếp tục tăng: delta tính trên mốc exp0 đã lưu (3).
        self.assertEqual(self.store.meter_today(self.DAY, 8.0, 6.0), (3.0, 3.0))
        self.assertEqual(self._baseline(), (5.0, 3.0))

    def test_recovery_survives_reopening_store(self):
        # Lần đọc đầu chỉ có bán, sau đó ĐÓNG store.
        self.assertEqual(self.store.meter_today(self.DAY, None, 10.0), (None, 0.0))
        self.assertEqual(self._baseline(), (None, 10.0))
        del self.store

        # Mở lại store trên cùng file -> import có số phải lấp được mốc NULL đã lưu.
        self.store = HistoryStore(self.path)
        self._set_buy(0.0)
        self.assertEqual(self.store.meter_today(self.DAY, 15.0, 20.0), (0.0, 10.0))
        self.assertEqual(self._baseline(), (15.0, 10.0))

    def test_both_counters_present_from_start_still_works(self):
        # Trường bình thường: cả hai mốc được seed ngay lần đầu, delta đúng.
        self._set_buy(2.0)
        self.assertEqual(self.store.meter_today(self.DAY, 5.0, 3.0), (2.0, 0.0))
        self.assertEqual(self._baseline(), (3.0, 3.0))  # imp0 = 5 - 2, exp0 = 3
        self.assertEqual(self.store.meter_today(self.DAY, 9.0, 7.0), (6.0, 4.0))
        self.assertEqual(self._baseline(), (3.0, 3.0))

    def test_no_baseline_recorded_when_no_counter(self):
        # Không có số công tơ nào -> (None, None), không ghi bất kỳ mốc nào.
        self.assertEqual(self.store.meter_today(self.DAY, None, None), (None, None))
        self.assertIsNone(self._baseline())

    def test_populated_path_skips_daily_query_and_write(self):
        # Đường đọc đủ mốc (both imp0/exp0 đã có) phải NHẸ: không hỏi daily.buy,
        # không ghi lại meter_baseline. Kiểm tra trắng (white-box) bằng cách theo dõi
        # câu lệnh SQL thực tế trên connection của store.
        self._set_buy(2.0)
        self.assertEqual(self.store.meter_today(self.DAY, 5.0, 3.0), (2.0, 0.0))  # tạo mốc

        executed = []
        real_connect = sqlite3.connect

        def spy_connect(*args, **kwargs):
            con = real_connect(*args, **kwargs)
            con.set_trace_callback(executed.append)
            return con

        with mock.patch("sqlite3.connect", side_effect=spy_connect):
            # Lần đọc thứ 2 là đường đủ mốc.
            self.assertEqual(self.store.meter_today(self.DAY, 9.0, 7.0), (6.0, 4.0))

        statements = [" ".join(sql.upper().split()) for sql in executed]
        self.assertTrue(statements, "expected to observe the baseline query")
        self.assertFalse(any("FROM DAILY" in sql for sql in statements), statements)
        self.assertFalse(
            any(sql.startswith(("INSERT ", "UPDATE ", "REPLACE ", "DELETE ")) for sql in statements),
            statements,
        )
