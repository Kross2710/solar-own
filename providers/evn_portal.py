"""Nguồn phụ EVN — đọc số liệu THẬT từ cổng CSKH EVNHCMC (API không chính thức).

Đối chiếu/hiệu chuẩn cho dashboard: kWh mua lưới + chỉ số công tơ theo NGÀY, và
HÓA ĐƠN tiền điện từng kỳ (số tiền EVN tính thật). KHÔNG thay SEMS — chỉ là nguồn
ground-truth ghi vào bảng riêng (evn_daily, evn_bills).

Luồng (đối chiếu source nestup_evn + probe thật 2026-06):
  1) POST /Dangnhap/checkLG  body form {u, p}  -> cookie `evn_session` (httpx tự giữ).
  2) Các call sau gửi kèm cookie; nếu hết phiên -> state 'error_login' -> tự login lại.

Lưu ý quan trọng:
  * Cần TÀI KHOẢN cổng (SĐT/email + mật khẩu), KHÁC mã KH. Thiếu phiên -> error_login.
  * EVN CHẶN IP nước ngoài -> phải chạy từ host HCMC / mạng VN.
  * Dữ liệu mức NGÀY, trễ ~6h -> nguồn đối chiếu hằng ngày, KHÔNG real-time.
  * RIÊNG TƯ: dashboard public/không-auth. Cổng lộ tên+địa chỉ thật qua endpoint
    `lichghithu` -> module này TUYỆT ĐỐI KHÔNG gọi nó. Chỉ giữ kWh/chỉ số/tiền,
    VỨT mọi trường định danh ngay từ lúc parse.
  * Số học theo từng endpoint KHÁC định dạng:
      - daily  Tong/tong_p_giao : "11,704.90" (phẩy ngăn nghìn, chấm thập phân)
      - bills  TONG_TIEN        : "3529591.00" (US: chấm thập phân, không ngăn nghìn)
      - payments tongTien       : "3.959.323"  (VN: CHẤM ngăn nghìn) -> bỏ chấm
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from .base import VN_TZ

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _num(s) -> Optional[float]:
    """Số kiểu '11,704.90' / '3.42' / '1034.00' -> float (bỏ phẩy ngăn nghìn)."""
    if s is None:
        return None
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _vnd(s) -> Optional[int]:
    """Tiền VN kiểu '3.959.323' (chấm ngăn nghìn) -> 3959323. Bỏ mọi '.'/','/khoảng trắng."""
    if s is None:
        return None
    try:
        return int(str(s).replace(".", "").replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return None


def _iso_day(s) -> Optional[str]:
    """'dd/mm/yyyy' (có thể kèm ' HH:MM:SS') -> 'yyyy-mm-dd'."""
    if not s:
        return None
    try:
        d = str(s).strip().split(" ")[0]
        dd, mm, yy = (int(x) for x in d.split("/"))
        if len(str(yy)) != 4:
            return None
        return f"{yy:04d}-{mm:02d}-{dd:02d}"
    except Exception:
        return None


def _cycle(s) -> Optional[str]:
    """Kỳ hóa đơn 'MM/YYYY' -> 'YYYY-MM'."""
    if not s:
        return None
    try:
        mm, yy = (int(x) for x in str(s).strip().split("/"))
        return f"{yy:04d}-{mm:02d}"
    except Exception:
        return None


class EvnPortal:
    name = "evnhcmc"

    def __init__(self, customer_id: str, username: str, password: str,
                 base_url: str = "https://cskh.evnhcmc.vn",
                 backfill_start_year: int = 2022):
        self.customer_id = customer_id
        self.username = username
        self.password = password
        self.base = base_url.rstrip("/")
        self.backfill_start_year = int(backfill_start_year)
        # cookie evn_session do httpx tự lưu trong cookie jar của client
        self._client = httpx.AsyncClient(timeout=30.0, headers={"User-Agent": UA})
        self._logged_in = False

    async def close(self) -> None:
        await self._client.aclose()

    # ---------- HTTP nền ----------
    async def login(self, force: bool = False) -> bool:
        if self._logged_in and not force:
            return True
        r = await self._client.post(self.base + "/Dangnhap/checkLG",
                                    data={"u": self.username, "p": self.password})
        j = r.json()
        if j.get("state") in ("success", "login"):
            self._logged_in = True
            return True
        self._logged_in = False
        raise RuntimeError(f"EVN login thất bại: {j.get('alert') or j.get('state')}")

    async def _post(self, path: str, data: dict, _retry: bool = True) -> dict:
        """POST form + tự login lại 1 lần nếu hết phiên (error_login)."""
        if not self._logged_in:
            await self.login()
        r = await self._client.post(self.base + path, data=data)
        j = r.json()
        if j.get("state") == "error_login" and _retry:
            self._logged_in = False
            await self.login(force=True)
            return await self._post(path, data, _retry=False)
        return j

    # ---------- lấy dữ liệu (CHỈ kWh/chỉ số/tiền — không trường định danh) ----------
    async def fetch_daily(self, frm: date, to: date) -> dict:
        """kWh mua + chỉ số công tơ theo ngày. -> {'YYYY-MM-DD': {'kwh','index'}}."""
        j = await self._post("/Tracuu/ajax_dienNangTieuThuTheoNgay", {
            "input_makh": self.customer_id,
            "input_tungay": frm.strftime("%d/%m/%Y"),
            "input_denngay": to.strftime("%d/%m/%Y"),
        })
        out: dict = {}
        if j.get("state") != "success":
            return out
        for row in (j.get("data") or {}).get("sanluong_tungngay", []):
            day = _iso_day(row.get("ngayFull"))
            if not day:
                continue
            out[day] = {"kwh": _num(row.get("Tong")),
                        "index": _num(row.get("tong_p_giao"))}
        return out

    async def fetch_bills(self) -> dict:
        """Hóa đơn từng kỳ (rolling ~12 kỳ). -> {'YYYY-MM': {'kwh','amount'}}."""
        j = await self._post("/Tracuu/ajax_dienNangTieuThuTheoKyHoaDon",
                             {"input_makh": self.customer_id})
        out: dict = {}
        if j.get("state") != "success":
            return out
        for row in (j.get("data") or {}).get("sanluong_hoadon", []):
            c = _cycle(row.get("NAME_FULL"))
            if not c:
                continue
            out[c] = {"kwh": _num(row.get("SAN_LUONG")),
                      "amount": _num(row.get("TONG_TIEN"))}  # TONG_TIEN = US format
        return out

    async def fetch_payments(self) -> dict:
        """Lịch sử thanh toán (~53 kỳ, sâu hơn bills). -> {'YYYY-MM': {'amount','paid_date'}}."""
        j = await self._post("/Tracuu/ajax_ds_lichSuThanhToan",
                             {"input_makh": self.customer_id})
        out: dict = {}
        if j.get("state") != "success":
            return out
        for row in (j.get("data") or {}).get("ds_hoadon", []):
            try:
                c = f"{int(row.get('NAM')):04d}-{int(row.get('THANG')):02d}"
            except (TypeError, ValueError):
                continue
            out[c] = {"amount": _vnd(row.get("tongTien")),  # tongTien = VN dot-thousand
                      "paid_date": _iso_day(row.get("ngayThu"))}
        return out

    async def _merged_bills(self) -> dict:
        """Gộp bills (kWh+tiền, 12 kỳ) với payments (tiền+ngày trả, 53 kỳ)."""
        out: dict = {}
        for c, v in (await self.fetch_bills()).items():
            out[c] = {"kwh": v.get("kwh"), "amount": v.get("amount"), "paid_date": None}
        for c, v in (await self.fetch_payments()).items():
            d = out.setdefault(c, {"kwh": None, "amount": None, "paid_date": None})
            if d.get("amount") is None:  # ưu tiên amount chính xác từ bills
                d["amount"] = v.get("amount")
            if v.get("paid_date"):
                d["paid_date"] = v.get("paid_date")
        return out

    # ---------- backfill / đồng bộ ----------
    async def backfill(self, store) -> dict:
        """Nạp toàn bộ: daily từ start_year -> nay (mỗi năm 1 request) + bills/payments."""
        await self.login()
        today = datetime.now(VN_TZ).date()
        days = 0
        for y in range(self.backfill_start_year, today.year + 1):
            frm = date(y, 1, 1)
            to = date(y, 12, 31) if y < today.year else today
            try:
                rows = await self.fetch_daily(frm, to)
                store.evn_backfill_daily(rows)
                days += len(rows)
            except Exception as e:
                print(f"  [evn] lỗi daily {y}: {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(0.5)  # né rate-limit cổng
        nb = store.evn_backfill_bills(await self._merged_bills())
        return {"days": days, "bills": nb}

    async def sync_recent(self, store, days: int = 45) -> dict:
        """Đồng bộ cửa sổ ngắn gần đây (chạy định kỳ): daily N ngày + bills/payments."""
        await self.login()
        today = datetime.now(VN_TZ).date()
        rows = await self.fetch_daily(today - timedelta(days=days), today)
        store.evn_backfill_daily(rows)
        nb = store.evn_backfill_bills(await self._merged_bills())
        return {"days": len(rows), "bills": nb}