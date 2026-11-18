"""Lưu lịch sử số liệu vào SQLite (file, không cần server DB riêng).

Ghi tối đa 1 dòng/phút (khử trùng theo phút). Dùng cho biểu đồ: mở trang là có
sẵn đường cong, và dữ liệu sống sót qua restart server.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from providers.base import VN_TZ


class HistoryStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        con = sqlite3.connect(self.path)
        con.execute(
            """CREATE TABLE IF NOT EXISTS samples(
                 minute TEXT PRIMARY KEY,
                 ts     TEXT,
                 pv     REAL,
                 load   REAL,
                 grid   REAL,
                 soc    REAL,
                 today  REAL
               )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS daily(
                 day TEXT PRIMARY KEY,
                 kwh REAL
               )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS curtailment(
                 day     TEXT PRIMARY KEY,
                 lost    REAL,
                 full_at TEXT
               )"""
        )
        # Sức khoẻ pin theo ngày (cho biểu đồ xu hướng SOH/throughput dài hạn). KHÔNG prune —
        # vài trăm dòng rất nhẹ. soh = giá trị MỚI NHẤT trong ngày (đổi rất chậm); charge/discharge
        # là throughput LŨY KẾ ĐỜI PIN (đơn điệu tăng) -> dùng MAX để không bao giờ tụt.
        con.execute(
            """CREATE TABLE IF NOT EXISTS battery_daily(
                 day        TEXT PRIMARY KEY,
                 soh        REAL,
                 charge_total    REAL,
                 discharge_total REAL
               )"""
        )
        # Thời tiết ngày (open-meteo) — đặc trưng để huấn luyện mô hình dự báo sản lượng.
        # Lưu lại mọi ngày đã thấy -> lịch sử thời tiết tích luỹ vĩnh viễn dù API chỉ
        # cho cửa sổ ngắn (past_days<=92). Khoá theo ngày, ghi đè bằng lần lấy mới nhất.
        con.execute(
            """CREATE TABLE IF NOT EXISTS weather_daily(
                 day       TEXT PRIMARY KEY,
                 rad       REAL,   -- shortwave_radiation_sum (MJ/m2)
                 sun       REAL,   -- sunshine_duration (s)
                 daylight  REAL,   -- daylight_duration (s)
                 tmax      REAL,
                 tmean     REAL,
                 tmin      REAL,
                 precip    REAL,   -- precipitation_sum (mm)
                 precip_h  REAL,   -- precipitation_hours
                 et0       REAL,   -- et0_fao_evapotranspiration
                 uv        REAL,   -- uv_index_max
                 wcode     INTEGER,
                 rain_prob REAL,   -- precipitation_probability_max
                 is_fcst   INTEGER -- 1 nếu là dự báo tương lai (chưa có thực đo)
               )"""
        )
        # EVN CSKH (ground-truth từ công tơ điện lực) — bảng RIÊNG, KHÔNG trộn vào `daily`
        # (daily.buy là ước tính từ SEMS; evn_daily.kwh là số công tơ EVN đo thật -> đối chiếu).
        # KHÔNG lưu trường ĐỊNH DANH (tên/địa chỉ) — chỉ kWh/chỉ số/tiền.
        con.execute(
            """CREATE TABLE IF NOT EXISTS evn_daily(
                 day         TEXT PRIMARY KEY,
                 kwh         REAL,   -- kWh mua lưới/ngày (Tong)
                 meter_index REAL    -- chỉ số công tơ luỹ kế (tong_p_giao)
               )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS evn_bills(
                 cycle     TEXT PRIMARY KEY,  -- 'YYYY-MM'
                 kwh       REAL,
                 amount    REAL,             -- TONG_TIEN (đ, gồm VAT) — hoá đơn thật
                 paid_date TEXT
               )"""
        )
        # Mốc CÔNG TƠ lúc nửa đêm (cho provider local): meter_e_total_imp/exp là số LŨY KẾ
        # đời hệ (đơn điệu tăng), nên mua/bán hôm nay = giá trị hiện tại - mốc đầu ngày. Lưu
        # bền để sống sót qua restart giữa ngày (khỏi tính lại từ lúc khởi động -> thiếu số).
        con.execute(
            """CREATE TABLE IF NOT EXISTS meter_baseline(
                 day  TEXT PRIMARY KEY,
                 imp0 REAL,   -- công tơ mua (kWh) tại 0h
                 exp0 REAL    -- công tơ bán (kWh) tại 0h
               )"""
        )
        # Proactive notices: one row per (kind, dkey) so a rule can't fire twice for the same
        # event; `expires` hides stale ones, `dismissed` is the user's "got it".
        con.execute(
            """CREATE TABLE IF NOT EXISTS notices(
                 id        INTEGER PRIMARY KEY AUTOINCREMENT,
                 ts        TEXT,
                 kind      TEXT,
                 dkey      TEXT,
                 severity  TEXT,
                 data      TEXT,
                 expires   TEXT,
                 dismissed INTEGER DEFAULT 0,
                 UNIQUE(kind, dkey)
               )"""
        )

        # Migration: thêm cột tiêu thụ (cons) + mua lưới (buy) vào bảng daily nếu thiếu
        cols = {r[1] for r in con.execute("PRAGMA table_info(daily)").fetchall()}
        if "cons" not in cols:
            con.execute("ALTER TABLE daily ADD COLUMN cons REAL")
        if "buy" not in cols:
            con.execute("ALTER TABLE daily ADD COLUMN buy REAL")
        con.commit()
        con.close()
        # Trạng thái chống "kẹt số" lúc giao ngày (xem _esc_stale): theo dõi cons của
        # khối energeStatisticsCharts để phát hiện SEMS đã reset sang ngày mới hay chưa.
        self._eday: Optional[str] = None       # ngày đang tích luỹ esc
        self._eprev_cons: Optional[float] = None  # cons cuối ngày trước (mốc dò reset)
        self._elast_cons: Optional[float] = None  # cons mới nhất đã thấy
        self._eok = True                        # đã xác nhận esc reset cho _eday?

    def _esc_stale(self, day: str, cons: Optional[float]) -> bool:
        """True nếu esc (cons/buy) còn đang trả số NGÀY HÔM QUA ngay sau khi giao ngày.

        SEMS reset khối energeStatisticsCharts TRỄ vài phút so với mốc 0h: sau nửa đêm
        nó vẫn trả tổng cuối ngày hôm qua trong khi `kpi.today` (sản lượng) đã reset sạch.
        Nếu ghi số trễ đó vào hàng `daily` hôm nay thì MAX(COALESCE...) sẽ CHỐT CỨNG số
        hôm qua (không hạ xuống được) -> tiêu thụ/mua/tiết kiệm hôm nay bị thổi phồng cả ngày.

        Chiến lược: sau khi sang ngày mới, BỎ QUA cons/buy cho tới khi thấy esc tụt mạnh
        (xác nhận đã reset về ~0), rồi mới cho ghi lại bình thường. Trạng thái nằm trong
        bộ nhớ nên nếu restart server đúng vào cửa sổ trễ (vài phút/ngày) thì vẫn có thể
        lọt — chấp nhận được so với việc trước đây dính 100% mỗi sáng.
        """
        if day != self._eday:
            # sang ngày mới: lấy cons cuối cùng của ngày trước làm mốc so sánh reset
            self._eprev_cons = self._elast_cons
            self._eday = day
            self._eok = self._eprev_cons is None  # chưa có mốc (lần đầu chạy) -> tin luôn
        if cons is not None:
            self._elast_cons = cons
        if self._eok:
            return False
        if cons is None:
            return False  # không có số để xét -> để nhịp sau quyết
        if cons < self._eprev_cons - 0.05: # type: ignore
            self._eok = True  # esc đã reset -> từ giờ ghi bình thường
            return False
        return True  # vẫn là tổng hôm qua -> bỏ qua, đừng chốt vào hàng hôm nay

    def record(self, m: dict) -> None:
        ts = m.get("timestamp")
        if not ts or m.get("status") != "online":
            return
        minute = str(ts)[:16]  # YYYY-MM-DDTHH:MM
        con = sqlite3.connect(self.path)
        con.execute(
            "INSERT OR REPLACE INTO samples(minute, ts, pv, load, grid, soc, today) VALUES (?,?,?,?,?,?,?)",
            (minute, ts, m.get("pv_power_w"), m.get("load_power_w"),
             m.get("grid_power_w"), m.get("battery_soc"), m.get("today_energy_kwh")),
        )
        # Ngày: giữ giá trị lớn nhất trong ngày (reset lúc 0h) cho sản lượng/tiêu thụ/mua
        day = str(ts)[:10]  # YYYY-MM-DD
        cons = m.get("today_consumption_kwh")
        buy = m.get("today_buy_kwh")
        # Sau giao ngày, esc của SEMS còn trả tổng hôm qua vài phút -> bỏ qua cons/buy
        # cho tới khi xác nhận đã reset (kwh không dính lỗi này nên vẫn ghi bình thường).
        if self._esc_stale(day, cons):
            cons = buy = None
        vals = {"kwh": m.get("today_energy_kwh"), "cons": cons, "buy": buy}
        if any(v is not None for v in vals.values()):
            con.execute("INSERT OR IGNORE INTO daily(day) VALUES (?)", (day,))
            for col, v in vals.items():
                if v is not None:
                    con.execute(
                        f"UPDATE daily SET {col}=MAX(COALESCE({col},0),?) WHERE day=?",
                        (float(v), day),
                    )
        # Sức khoẻ pin theo ngày: soh mới nhất + throughput lũy kế (MAX, đơn điệu tăng).
        soh = m.get("battery_soh")
        ch = m.get("battery_charge_total_kwh")
        dis = m.get("battery_discharge_total_kwh")
        if any(v is not None for v in (soh, ch, dis)):
            con.execute("INSERT OR IGNORE INTO battery_daily(day) VALUES (?)", (day,))
            if soh is not None:
                con.execute("UPDATE battery_daily SET soh=? WHERE day=?", (float(soh), day))
            if ch is not None:
                con.execute("UPDATE battery_daily SET charge_total=MAX(COALESCE(charge_total,0),?) WHERE day=?",
                            (float(ch), day))
            if dis is not None:
                con.execute("UPDATE battery_daily SET discharge_total=MAX(COALESCE(discharge_total,0),?) WHERE day=?",
                            (float(dis), day))
        con.commit()
        con.close()

    def recent(self, hours: int = 12) -> list[dict]:
        """Đường cong phút của `hours` giờ GẦN NHẤT (neo theo mẫu mới nhất trong bảng).

        Phải lọc theo THỜI GIAN chứ không chỉ LIMIT N×60 dòng: sau khi host tắt lâu
        (mẫu thưa / lỗ thủng chỉ vá 5 phút/điểm), "N dòng mới nhất" trải ra hàng
        TUẦN — buffer frontend ôm cả dữ liệu cũ rích. Neo theo MAX(minute) thay vì
        đồng hồ thực để lúc mới khởi động (chưa có mẫu mới) vẫn trả đoạn cuối cùng
        trước khi tắt. LIMIT giữ lại làm chặn trên.
        """
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT ts, pv, load, grid, soc FROM samples "
            "WHERE minute >= (SELECT strftime('%Y-%m-%dT%H:%M', MAX(minute), ?) FROM samples) "
            "ORDER BY minute DESC LIMIT ?",
            (f"-{max(1, hours)} hours", max(1, hours) * 60),
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        rows.reverse()  # cũ -> mới
        return rows

    def meter_today(self, day: str, cur_imp: Optional[float],
                    cur_exp: Optional[float]) -> tuple:
        """Mua/bán HÔM NAY từ công tơ CT lũy kế (`meter_e_total_imp/exp`) của provider local.

        = giá trị hiện tại - MỐC NỬA ĐÊM. Mốc lưu bền trong `meter_baseline`:
        - Lần đầu trong ngày: seed mốc = công tơ hiện tại TRỪ phần buy đã ghi cho hôm nay
          (từ SEMS/`daily.buy`) -> mua hôm nay khớp NGAY cả khi server khởi động giữa ngày
          (vd deploy lúc trưa). Bán seed 0 (VN không FIT, bán ~0).
        Trả (today_buy, today_sell) kWh (>=0), hoặc None nếu không có số công tơ.
        """
        if cur_imp is None and cur_exp is None:
            return (None, None)
        con = sqlite3.connect(self.path)
        row = con.execute("SELECT imp0, exp0 FROM meter_baseline WHERE day=?", (day,)).fetchone()
        if row is None:
            dr = con.execute("SELECT buy FROM daily WHERE day=?", (day,)).fetchone()
            seed_buy = float(dr[0]) if (dr and dr[0] is not None) else 0.0
            imp0 = None if cur_imp is None else float(cur_imp) - seed_buy
            exp0 = None if cur_exp is None else float(cur_exp)
            con.execute("INSERT OR REPLACE INTO meter_baseline(day, imp0, exp0) VALUES (?,?,?)",
                        (day, imp0, exp0))
            con.commit()
        else:
            imp0, exp0 = row
        con.close()
        buy = None if (cur_imp is None or imp0 is None) else max(0.0, round(float(cur_imp) - float(imp0), 1))
        sell = None if (cur_exp is None or exp0 is None) else max(0.0, round(float(cur_exp) - float(exp0), 1))
        return (buy, sell)

    @staticmethod
    def _local_today() -> str:
        """Hôm nay theo giờ VN (YYYY-MM-DD) — mốc để backfill BỎ QUA hàng hôm nay."""
        return datetime.now(VN_TZ).date().isoformat()

    def backfill_daily(self, rows: dict, _today: Optional[str] = None) -> int:
        """Nạp sản lượng ngày lấy từ SEMS vào bảng `daily`.

        Dùng cho lịch sử dài hạn: lấp các ngày server không chạy và cả những
        ngày TRƯỚC khi có dashboard. Giữ giá trị lớn hơn (max) để không bao giờ
        làm giảm số đã có. rows = {'YYYY-MM-DD': kwh}.

        BỎ QUA hàng HÔM NAY (>= hôm nay): hôm nay do nguồn LIVE (`record()`) độc
        quyền ghi — provider local đọc counter reset-nửa-đêm sạch, khỏi tranh MAX
        với số SEMS (chống xung đột dual-provider). Ngày cũ vẫn do backfill lấp.
        """
        if not rows:
            return 0
        today = _today or self._local_today()
        con = sqlite3.connect(self.path)
        for day, kwh in rows.items():
            d = str(day)[:10]
            if d >= today:
                continue
            con.execute("INSERT OR IGNORE INTO daily(day) VALUES (?)", (d,))
            con.execute("UPDATE daily SET kwh=MAX(COALESCE(kwh,0),?) WHERE day=?",
                        (float(kwh), d))
        con.commit()
        n = con.total_changes
        con.close()
        return n

    def backfill_energy(self, rows: dict) -> int:
        """Nạp TIÊU THỤ + MUA LƯỚI từng ngày từ SEMS. rows={'YYYY-MM-DD':{'cons','buy'}}.

        KHÁC `backfill_daily`: hàm này GHI CẢ HÔM NAY. `buy` (mua lưới) phải theo CÔNG TƠ
        điện lực (EVN tính tiền), mà provider local KHÔNG cấp đúng (inverter `e_day_imp` đo
        ở đầu cực AC, không phải công tơ CT — bỏ sót lưới sạc pin). Nên SEMS (dựa công tơ,
        đã kiểm chứng khớp hoá đơn EVN) là nguồn DUY NHẤT cho cons/buy hàng ngày, kể cả hôm
        nay. Local chỉ sở hữu `kwh` (sản lượng) của hôm nay qua `record()`. Xem Decisions.
        """
        if not rows:
            return 0
        con = sqlite3.connect(self.path)
        for day, v in rows.items():
            d = str(day)[:10]
            con.execute("INSERT OR IGNORE INTO daily(day) VALUES (?)", (d,))
            if v.get("cons") is not None:
                con.execute("UPDATE daily SET cons=MAX(COALESCE(cons,0),?) WHERE day=?",
                            (float(v["cons"]), d))
            if v.get("buy") is not None:
                con.execute("UPDATE daily SET buy=MAX(COALESCE(buy,0),?) WHERE day=?",
                            (float(v["buy"]), d))
        con.commit()
        n = con.total_changes
        con.close()
        return n

    def backfill_samples(self, day: str, points: list) -> int:
        """Lấp LỖ THỦNG đường cong phút (`samples`) bằng đường cong 5 phút của SEMS.

        Host tắt (cúp điện, reboot, deploy) -> `samples` mất trắng khoảng đó, trong khi
        `daily` vẫn đúng nhờ backfill từ SEMS -> biểu đồ trong ngày LỆCH với con số tổng
        (vd cúp điện 2026-08-07: mất 23:36→07:04, tải hôm nay nhìn hụt 7 tiếng).
        `GetPlantPowerChart` có đủ pv/load/grid/soc cả ngày nên lấp lại được.

        INSERT OR IGNORE theo khoá `minute`: chỉ điền phút CÒN THIẾU, không bao giờ đè
        mẫu local (độ phân giải 1 phút, chính xác hơn mốc 5 phút của SEMS). Cột `today`
        để NULL — đường cong không cấp số luỹ kế, và không consumer nào đọc cột này.
        points = [{'t':'HH:MM','pv','load','grid','soc'}, ...] từ `fetch_day_curve`.
        """
        if not points:
            return 0
        d = str(day)[:10]
        con = sqlite3.connect(self.path)
        for p in points:
            t = str(p.get("t") or "")[:5]
            if len(t) != 5 or t[2] != ":":
                continue
            # Điểm rỗng hoàn toàn (ngày tương lai / trước khi hệ chạy) -> bỏ, đừng tạo
            # hàng NULL làm gãy biểu đồ.
            if all(p.get(k) is None for k in ("pv", "load", "grid", "soc")):
                continue
            con.execute(
                "INSERT OR IGNORE INTO samples(minute, ts, pv, load, grid, soc, today) "
                "VALUES (?,?,?,?,?,?,NULL)",
                (f"{d}T{t}", f"{d}T{t}:00+07:00",
                 p.get("pv"), p.get("load"), p.get("grid"), p.get("soc")),
            )
        con.commit()
        n = con.total_changes
        con.close()
        return n

    # ---------- EVN CSKH (ground-truth từ công tơ điện lực) ----------
    def evn_backfill_daily(self, rows: dict) -> int:
        """kWh mua + chỉ số công tơ THẬT theo ngày. rows={'YYYY-MM-DD':{'kwh','index'}}.

        MAX(COALESCE) như `daily`: số trong ngày chỉ tăng, chỉ số đơn điệu tăng -> không tụt.
        """
        if not rows:
            return 0
        con = sqlite3.connect(self.path)
        for day, v in rows.items():
            d = str(day)[:10]
            con.execute("INSERT OR IGNORE INTO evn_daily(day) VALUES (?)", (d,))
            if v.get("kwh") is not None:
                con.execute("UPDATE evn_daily SET kwh=MAX(COALESCE(kwh,0),?) WHERE day=?",
                            (float(v["kwh"]), d))
            if v.get("index") is not None:
                con.execute("UPDATE evn_daily SET meter_index=MAX(COALESCE(meter_index,0),?) WHERE day=?",
                            (float(v["index"]), d))
        con.commit()
        con.close()
        return len(rows)  # số NGÀY đã xử lý (total_changes phồng vì đếm cả UPDATE idempotent)

    def evn_backfill_bills(self, rows: dict) -> int:
        """Hoá đơn EVN từng kỳ. rows={'YYYY-MM':{'kwh','amount','paid_date'}}.

        Hoá đơn đã chốt là số CUỐI -> ghi đè bằng giá trị mới nhất (khác `daily` dùng MAX);
        chỉ cập nhật cột CÓ giá trị để NULL không xoá số đã có.
        """
        if not rows:
            return 0
        con = sqlite3.connect(self.path)
        for cycle, v in rows.items():
            c = str(cycle)[:7]
            con.execute("INSERT OR IGNORE INTO evn_bills(cycle) VALUES (?)", (c,))
            for col in ("kwh", "amount", "paid_date"):
                if v.get(col) is not None:
                    val = v[col] if col == "paid_date" else float(v[col])
                    con.execute(f"UPDATE evn_bills SET {col}=? WHERE cycle=?", (val, c))
        con.commit()
        con.close()
        return len(rows)  # số KỲ đã xử lý (total_changes phồng vì đếm cả UPDATE idempotent)

    def evn_daily_all(self, days: int = 4000) -> list[dict]:
        """[{day, kwh, meter_index}] (cũ -> mới)."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT day, kwh, meter_index FROM evn_daily ORDER BY day DESC LIMIT ?",
            (max(1, days),))
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        rows.reverse()
        return rows

    def evn_bills_all(self) -> list[dict]:
        """[{cycle, kwh, amount, paid_date}] (cũ -> mới)."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute("SELECT cycle, kwh, amount, paid_date FROM evn_bills ORDER BY cycle")
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows

    def evn_counts(self) -> dict:
        con = sqlite3.connect(self.path)
        d = con.execute("SELECT COUNT(*) FROM evn_daily").fetchone()[0]
        b = con.execute("SELECT COUNT(*) FROM evn_bills").fetchone()[0]
        con.close()
        return {"daily": int(d), "bills": int(b)}

    # Pin xả/ngày (kWh) từ CÔNG TƠ LŨY KẾ đời pin (battery_daily.discharge_total, MAX-upsert
    # đơn điệu tăng): batt_out(N) = dis(N) - dis(N-1). Chỉ tin khi 2 ngày LIỀN KỀ (gap=1 —
    # thiếu ngày giữa thì hiệu ôm nhiều ngày, chia không được) và hiệu >= 0 (counter reset
    # firmware/thay pin -> âm -> bỏ). Ngày thiếu -> NULL, frontend tự gộp pin vào solar.
    _BATT_OUT_CTE = (
        "WITH bo AS (SELECT day, "
        "discharge_total - LAG(discharge_total) OVER (ORDER BY day) AS d, "
        "julianday(day) - julianday(LAG(day) OVER (ORDER BY day)) AS gap "
        "FROM battery_daily WHERE discharge_total IS NOT NULL) "
    )

    def daily_full(self, days: int = 400) -> list[dict]:
        """Trả [{day, kwh, cons, buy, batt}] (cũ -> mới) cho tính tiền theo bậc thang.

        batt = kWh pin xả trong ngày (xem _BATT_OUT_CTE); NULL nếu không suy được.
        """
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            self._BATT_OUT_CTE
            + "SELECT dl.day, dl.kwh, dl.cons, dl.buy, "
            "CASE WHEN bo.gap = 1.0 AND bo.d >= 0 THEN round(bo.d, 2) END AS batt "
            "FROM daily dl LEFT JOIN bo ON bo.day = dl.day "
            "ORDER BY dl.day DESC LIMIT ?",
            (max(1, days),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        rows.reverse()
        return rows

    def first_generation_day(self) -> str | None:
        """Ngày đầu tiên có sản lượng (≈ ngày lắp solar), 'YYYY-MM-DD' hoặc None."""
        con = sqlite3.connect(self.path)
        row = con.execute("SELECT MIN(day) FROM daily WHERE kwh > 0").fetchone()
        con.close()
        return row[0] if row else None

    def daily_count(self) -> int:
        con = sqlite3.connect(self.path)
        n = con.execute("SELECT COUNT(*) FROM daily").fetchone()[0]
        con.close()
        return int(n)

    def daily(self, days: int = 30) -> list[dict]:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT day, kwh FROM daily ORDER BY day DESC LIMIT ?", (max(1, days),)
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        rows.reverse()  # cũ -> mới
        return rows

    def monthly(self, months: int = 60) -> list[dict]:
        """Tổng hợp theo tháng từ bảng daily. [{month:'YYYY-MM', kwh, cons, buy, days, batt, batt_days}] cũ->mới.

        SUM bỏ qua NULL (trả NULL nếu cả tháng trống); COUNT(kwh) = số ngày có sản lượng.
        """
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            self._BATT_OUT_CTE
            + "SELECT substr(dl.day,1,7) AS month, SUM(dl.kwh) AS kwh, SUM(dl.cons) AS cons, "
            "SUM(dl.buy) AS buy, COUNT(dl.kwh) AS days, COUNT(dl.cons) AS cons_days, "
            "COUNT(dl.buy) AS buy_days, "
            # batt tháng: chỉ cộng ngày suy được; batt_days cho frontend biết ĐỘ PHỦ
            # (phủ mỏng -> đừng tách pin, gộp vào solar cho trung thực)
            "SUM(CASE WHEN bo.gap = 1.0 AND bo.d >= 0 THEN bo.d END) AS batt, "
            "COUNT(CASE WHEN bo.gap = 1.0 AND bo.d >= 0 THEN 1 END) AS batt_days "
            "FROM daily dl LEFT JOIN bo ON bo.day = dl.day "
            "GROUP BY month ORDER BY month DESC LIMIT ?",
            (max(1, months),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        rows.reverse()  # cũ -> mới
        return rows

    def yearly(self) -> list[dict]:
        """Tổng hợp theo năm từ bảng daily. [{year:'YYYY', kwh, cons, buy, days}] cũ->mới."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT substr(day,1,4) AS year, SUM(kwh) AS kwh, SUM(cons) AS cons, "
            "SUM(buy) AS buy, COUNT(kwh) AS days, COUNT(cons) AS cons_days, "
            "COUNT(buy) AS buy_days FROM daily GROUP BY year ORDER BY year"
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows

    def night_load_avg_kwh(self, days: int = 14) -> Optional[float]:
        """Ước tiêu thụ ban đêm (18h→6h) trung bình mỗi đêm = AVG(load) × 12h, từ samples gần đây.

        Mốc cắt tính phía Python theo GIỜ VN — date('now') của SQLite là UTC, lệch 7h
        so với chuỗi ts lưu giờ địa phương (quanh 0h–7h VN sẽ lọt thêm/thiếu 1 ngày).
        """
        cutoff = (datetime.now(VN_TZ) - timedelta(days=max(1, days))).date().isoformat()
        con = sqlite3.connect(self.path)
        cur = con.execute(
            "SELECT AVG(load) FROM samples "
            "WHERE load IS NOT NULL AND substr(ts,1,10) >= ? "
            "AND (CAST(substr(ts,12,2) AS INTEGER) >= 18 OR CAST(substr(ts,12,2) AS INTEGER) < 6)",
            (cutoff,),
        )
        avg = cur.fetchone()[0]
        con.close()
        if avg is None:
            return None
        return round(avg / 1000.0 * 12.0, 1)  # 12 giờ đêm

    def hourly_profile(self, days: int = 30) -> list[dict]:
        """Hồ sơ 24 giờ: TB pv/load/grid theo từng giờ trong ngày (từ samples N ngày gần nhất)."""
        cutoff = (datetime.now(VN_TZ) - timedelta(days=max(1, days))).date().isoformat()
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT CAST(substr(ts,12,2) AS INTEGER) AS h, AVG(pv) AS pv, AVG(load) AS load, "
            "AVG(grid) AS grid, COUNT(*) AS n FROM samples "
            "WHERE ts IS NOT NULL AND substr(ts,1,10) >= ? GROUP BY h",
            (cutoff,),
        )
        by = {int(r["h"]): r for r in cur.fetchall()}
        con.close()
        out = []
        for h in range(24):
            r = by.get(h)
            out.append({
                "hour": h,
                "pv": round(r["pv"]) if r and r["pv"] is not None else None,
                "load": round(r["load"]) if r and r["load"] is not None else None,
                "grid": round(r["grid"]) if r and r["grid"] is not None else None,
                "n": int(r["n"]) if r else 0,
            })
        return out

    def battery_trend(self, days: int = 400) -> list[dict]:
        """[{day, soh, charge_total, discharge_total}] (cũ -> mới) cho biểu đồ xu hướng pin."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT day, soh, charge_total, discharge_total FROM battery_daily "
            "ORDER BY day DESC LIMIT ?", (max(1, days),))
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        rows.reverse()
        return rows

    # ---------- curtailment (điện nắng bị bỏ phí) ----------
    def record_curtailment(self, day: str, lost: float, full_at) -> None:
        con = sqlite3.connect(self.path)
        con.execute(
            "INSERT INTO curtailment(day, lost, full_at) VALUES (?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET lost=excluded.lost, full_at=excluded.full_at",
            (str(day)[:10], float(lost or 0.0), full_at),
        )
        con.commit()
        con.close()

    def curtailment_days(self) -> set:
        con = sqlite3.connect(self.path)
        rows = con.execute("SELECT day FROM curtailment").fetchall()
        con.close()
        return {r[0] for r in rows}

    def curtailment_recent(self, days: int = 30) -> list[dict]:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT day, lost, full_at FROM curtailment ORDER BY day DESC LIMIT ?",
            (max(1, days),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        rows.reverse()
        return rows

    # ---------- notices ----------
    def notice_add(self, kind: str, dkey: str, severity: str, data: dict, expires: str) -> bool:
        """Insert unless (kind, dkey) already exists. True when a new notice was added."""
        ts = datetime.now(VN_TZ).strftime("%Y-%m-%dT%H:%M")
        con = sqlite3.connect(self.path)
        cur = con.execute(
            "INSERT OR IGNORE INTO notices(ts, kind, dkey, severity, data, expires) VALUES(?,?,?,?,?,?)",
            (ts, kind, dkey, severity, json.dumps(data, ensure_ascii=False), expires),
        )
        con.commit()
        added = cur.rowcount > 0
        con.close()
        return added

    def notices_recent(self, limit: int = 20, active_at: Optional[str] = None) -> list[dict]:
        """Newest first. With `active_at` (YYYY-MM-DDTHH:MM) only unexpired, undismissed ones."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        where = "WHERE dismissed = 0 AND expires > ?" if active_at else ""
        params: tuple = (active_at, max(1, limit)) if active_at else (max(1, limit),)
        cur = con.execute(
            f"SELECT id, ts, kind, dkey, severity, data, expires FROM notices {where} "
            "ORDER BY id DESC LIMIT ?",
            params,
        )
        rows = []
        for r in cur.fetchall():
            row = dict(r)
            try:
                row["data"] = json.loads(row["data"] or "{}")
            except Exception:
                row["data"] = {}
            rows.append(row)
        con.close()
        return rows

    def notice_dismiss(self, notice_id: int) -> bool:
        con = sqlite3.connect(self.path)
        cur = con.execute("UPDATE notices SET dismissed = 1 WHERE id = ?", (notice_id,))
        con.commit()
        changed = cur.rowcount > 0
        con.close()
        return changed

    # ---------- thời tiết ngày (đặc trưng cho dự báo sản lượng) ----------
    _WX_COLS = ("rad", "sun", "daylight", "tmax", "tmean", "tmin",
                "precip", "precip_h", "et0", "uv", "wcode", "rain_prob")

    def weather_upsert(self, rows: dict) -> int:
        """Ghi/đè thời tiết ngày. rows = {'YYYY-MM-DD': {col: val, 'is_fcst': 0/1}}."""
        if not rows:
            return 0
        con = sqlite3.connect(self.path)
        cols = self._WX_COLS + ("is_fcst",)
        ph = ",".join("?" for _ in ("day",) + cols)
        sql = (f"INSERT INTO weather_daily(day,{','.join(cols)}) VALUES ({ph}) "
               f"ON CONFLICT(day) DO UPDATE SET "
               + ",".join(f"{c}=excluded.{c}" for c in cols))
        for day, v in rows.items():
            d = str(day)[:10]
            con.execute(sql, (d, *[v.get(c) for c in cols]))
        con.commit()
        n = con.total_changes
        con.close()
        return n

    def weather_all(self) -> list[dict]:
        """Tất cả thời tiết ngày đã lưu (cũ -> mới)."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT day," + ",".join(self._WX_COLS) + ",is_fcst "
            "FROM weather_daily ORDER BY day")
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows

    def training_rows(self) -> list[dict]:
        """Ghép sản lượng ngày (daily.kwh) với thời tiết cùng ngày — bộ huấn luyện.

        Chỉ lấy ngày có CẢ kwh lẫn bức xạ và KHÔNG phải dự báo tương lai (is_fcst!=1).
        Trả [{day, kwh, rad, sun, ...}] cũ -> mới.
        """
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT d.day AS day, d.kwh AS kwh," + ",".join("w." + c for c in self._WX_COLS) +
            " FROM daily d JOIN weather_daily w ON w.day = d.day "
            "WHERE d.kwh IS NOT NULL AND w.rad IS NOT NULL "
            "AND COALESCE(w.is_fcst,0) = 0 ORDER BY d.day")
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows

    def load_training_rows(self) -> list[dict]:
        """Ghép TIÊU THỤ/MUA LƯỚI ngày với thời tiết — bộ huấn luyện cho chiếu hoá đơn.

        Khác training_rows (lấy kwh): lọc theo cons/buy có giá trị, không phải kwh.
        """
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT d.day AS day, d.cons AS cons, d.buy AS buy, "
            "w.tmax, w.tmean, w.rad, w.precip, w.daylight "
            "FROM daily d JOIN weather_daily w ON w.day = d.day "
            "WHERE (d.cons IS NOT NULL OR d.buy IS NOT NULL) AND w.tmean IS NOT NULL "
            "AND COALESCE(w.is_fcst,0) = 0 ORDER BY d.day")
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows

    def night_load_kwh(self, day: str) -> Optional[float]:
        """Tiêu thụ ĐÊM của MỘT đêm cụ thể = AVG(load) 18h ngày `day` -> 6h hôm sau, × 12h.

        Cùng công thức night_load_avg_kwh (để so sánh táo-với-táo trong rule cảnh báo
        "đêm qua dùng nhiều bất thường"). Trả None nếu đêm đó thiếu mẫu (< 2h dữ liệu).
        """
        from datetime import date as _date
        nxt = (_date.fromisoformat(day) + timedelta(days=1)).isoformat()
        con = sqlite3.connect(self.path)
        cur = con.execute(
            "SELECT AVG(load), COUNT(*) FROM samples WHERE load IS NOT NULL AND ("
            "(substr(ts,1,10) = ? AND CAST(substr(ts,12,2) AS INTEGER) >= 18) OR "
            "(substr(ts,1,10) = ? AND CAST(substr(ts,12,2) AS INTEGER) < 6))",
            (day, nxt),
        )
        avg, n = cur.fetchone()
        con.close()
        if avg is None or (n or 0) < 120:  # < ~2h mẫu phút -> không đủ tin
            return None
        return round(avg / 1000.0 * 12.0, 1)

    def prune(self, keep_days: int = 30) -> None:
        """Xoá CHỈ đường cong phút (`samples`) cũ hơn keep_days.

        Bảng `daily` (tổng ngày) KHÔNG bao giờ bị xoá — giữ lịch sử dài hạn
        vĩnh viễn (365 dòng/năm, rất nhẹ).
        """
        # Mốc cắt theo giờ VN, ĐÚNG định dạng của cột minute ("YYYY-MM-DDTHH:MM") —
        # datetime('now') của SQLite vừa là UTC (lệch 7h) vừa trả dấu cách thay chữ T
        # (so sánh chuỗi khác format là so lệch).
        cutoff = (datetime.now(VN_TZ) - timedelta(days=keep_days)).strftime("%Y-%m-%dT%H:%M")
        con = sqlite3.connect(self.path)
        con.execute("DELETE FROM samples WHERE minute < ?", (cutoff,))
        con.commit()
        con.close()
