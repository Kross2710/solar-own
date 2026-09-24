"""GoodWe SEMS+ gateway.

The classic portal call GetMonitorDetailByPowerstationId on /v2 now returns
an empty object with code 0. Live power, daily energy and the intraday curve
come from the SEMS+ gateway instead.

Login: POST {web}/web/sems/sems-user/api/v1/auth/cross-login
Password: base64(md5 hex). Each call sends X-Signature =
base64(sha256_hex("{ts}@{uid}@{token}") + "@" + ts).

Power signs on the wire, mapped to the app convention in providers.base:
    pGrid < 0 imports, pBat > 0 discharges.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from .base import Metrics, Provider, VN_TZ

REGIONS = {
    "hk": "https://hk-semsplus.goodwe.com",
    "eu": "https://eu-semsplus.goodwe.com",
    "au": "https://au-semsplus.goodwe.com",
    "us": "https://us-semsplus.goodwe.com",
    "cn": "https://cn-semsplus.goodwe.com",
}
TIME_OFFSETS = {"hk": 7, "auto": 7, "cn": 8, "au": 10, "eu": 1, "us": -5}
SUCCESS_CODES = {"0", "00000"}
WINDOW_DAYS = 7


def sems_password(password: str) -> str:
    digest = hashlib.md5(password.encode("utf-8")).hexdigest()
    return base64.b64encode(digest.encode("utf-8")).decode("ascii")


def sems_signature(uid: str, token: str, ts: int) -> str:
    digest = hashlib.sha256(f"{ts}@{uid}@{token}".encode("utf-8")).hexdigest()
    return base64.b64encode(f"{digest}@{ts}".encode("utf-8")).decode("ascii")


def _num(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _watts(kw: Optional[float], *, flip: bool = False) -> Optional[int]:
    if kw is None:
        return None
    watts = round(kw * 1000)
    return -watts if flip else watts


def _index_series(data_list: list) -> dict[str, dict[str, float]]:
    """{item: {timestamp: value}} from a statisticsAndPreV2 dataList."""
    series: dict[str, dict[str, float]] = {}
    for entry in data_list or []:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item")
        if not item:
            continue
        points: dict[str, float] = {}
        for sample in entry.get("powerData") or []:
            if not isinstance(sample, dict):
                continue
            stamp = sample.get("tp")
            value = _num(sample.get("power"))
            if stamp and value is not None:
                points[str(stamp)] = value
        series[str(item)] = points
    return series


def energy_by_day(data_list: list) -> dict[str, dict[str, float]]:
    """Integrate 1-minute kW samples into daily kWh.

    pGrid is negative while importing, so buy is the negative part and sell
    is the positive part. Each sample represents one minute.
    """
    series = _index_series(data_list)
    days: dict[str, dict[str, float]] = {}

    def bucket(day: str) -> dict[str, float]:
        return days.setdefault(day, {"pv": 0.0, "cons": 0.0, "buy": 0.0, "sell": 0.0})

    for stamp, power in series.get("pSystem", {}).items():
        bucket(stamp[:10])["pv"] += power
    for stamp, power in series.get("pConsum", {}).items():
        bucket(stamp[:10])["cons"] += power
    for stamp, power in series.get("pGrid", {}).items():
        row = bucket(stamp[:10])
        if power < 0:
            row["buy"] += -power
        elif power > 0:
            row["sell"] += power

    for row in days.values():
        for key, value in row.items():
            row[key] = round(value / 60, 3)
    return {day: row for day, row in days.items() if len(day) == 10}


def curve_points(data_list: list, *, step_minutes: int = 5) -> list[dict]:
    """Intraday points in watts. Battery +charge, grid +import."""
    series = _index_series(data_list)
    times = sorted(
        series.get("pSystem")
        or series.get("pConsum")
        or series.get("soc")
        or {}
    )
    points = []
    for stamp in times:
        if len(stamp) < 16:
            continue
        clock = stamp[11:16]
        try:
            minute = int(clock[3:5])
        except ValueError:
            continue
        if step_minutes > 1 and minute % step_minutes:
            continue

        def at(item: str, flip: bool = False) -> Optional[int]:
            value = series.get(item, {}).get(stamp)
            return _watts(value, flip=flip)

        soc = series.get("soc", {}).get(stamp)
        points.append({
            "t": clock,
            "pv": at("pSystem"),
            "load": at("pConsum"),
            "batt": at("pBat", flip=True),
            "grid": at("pGrid", flip=True),
            "soc": None if soc is None else round(soc),
        })
    return points


class CloudGoodWeProvider(Provider):
    name = "cloud"

    def __init__(
        self,
        account: str,
        password: str,
        region: str = "auto",
        station_id: Optional[str] = None,
        station_name: Optional[str] = None,
        capacity_kw: Optional[float] = None,
        min_refresh_s: int = 60,
        price_per_kwh: Optional[float] = None,
        currency: Optional[str] = None,
        battery_reserve_percent: float = 20,
    ):
        self.account = account
        self.password = password
        self.region = (region or "auto").lower()
        self.station_id = station_id or None
        self.station_name = station_name
        self.capacity_kw = capacity_kw
        self.price_per_kwh = price_per_kwh
        self.currency = currency
        self.battery_reserve_percent = battery_reserve_percent
        self.min_refresh_s = max(20, int(min_refresh_s))
        self._tz_offset = TIME_OFFSETS.get(self.region, 7)
        self._web = REGIONS.get(self.region if self.region != "auto" else "hk", REGIONS["hk"])
        self._api: Optional[str] = None
        self._session: Optional[dict] = None
        self._device_id = str(uuid.uuid4())
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache: Optional[Metrics] = None
        self._cache_at = 0.0
        self._station_profile: Optional[dict] = None
        self._profile_at = 0.0
        self._inverter_sn: Optional[str] = None
        self._month_kwh: Optional[float] = None
        self._month_at = 0.0
        self._energy_cache: dict[int, tuple[float, dict]] = {}
        self._day_cache: dict[str, tuple[float, dict]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self, token_json: str, uid: str = "", token: str = "") -> dict:
        ts = int(time.time() * 1000)
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": self._web,
            "Referer": f"{self._web}/",
            "User-Agent": "solar-dashboard",
            "currentLang": "en",
            "neutral": "0",
            "uuid": self._device_id,
            "token": token_json,
            "X-Signature": sems_signature(uid, token, ts),
        }

    async def _login(self) -> dict:
        empty = json.dumps({
            "uid": "",
            "timestamp": 0,
            "token": "",
            "client": "semsPlusWeb",
            "version": "",
            "language": "en",
        })
        response = await self._client.post(
            f"{self._web}/web/sems/sems-user/api/v1/auth/cross-login",
            headers=self._headers(empty),
            json={
                "account": self.account,
                "pwd": sems_password(self.password),
                "agreement": 1,
                "isLocal": False,
                "isChinese": False,
            },
        )
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        if str(body.get("code")) not in SUCCESS_CODES or not isinstance(data, dict):
            message = body.get("msg") or body.get("message") or body.get("code")
            raise RuntimeError(f"Đăng nhập SEMS+ thất bại ({message})")
        if not data.get("uid") or not data.get("token"):
            raise RuntimeError("SEMS+ không trả phiên đăng nhập")
        api = str(data.get("api") or "").rstrip("/")
        if not api:
            raise RuntimeError("SEMS+ không trả địa chỉ gateway")
        self._api = api
        self._session = data
        self._device_id = str(data.get("uuid") or self._device_id)
        return data

    def _token_header(self) -> str:
        session = self._session or {}
        return json.dumps({
            "uid": session.get("uid"),
            "timestamp": session.get("timestamp"),
            "token": session.get("token"),
            "client": session.get("client") or "semsPlusWeb",
            "version": session.get("version") or "",
            "language": session.get("language") or "en",
            "api": self._api,
            "region": session.get("region") or self.region,
            "uuid": self._device_id,
        })

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        retry: bool = True,
    ) -> dict:
        if self._session is None or self._api is None:
            await self._login()
        session = self._session or {}
        response = await self._client.request(
            method,
            f"{self._api}{path}",
            headers=self._headers(
                self._token_header(),
                str(session.get("uid") or ""),
                str(session.get("token") or ""),
            ),
            params=params,
            json=json_body,
        )
        body = response.json()
        code = str(body.get("code")) if isinstance(body, dict) else ""
        if code in SUCCESS_CODES:
            return body
        message = ""
        if isinstance(body, dict):
            message = str(body.get("msg") or body.get("message") or "")
        expired = code in {"100001", "100002"} or "token" in message.lower() or "login" in message.lower()
        if retry and expired:
            self._session = None
            await self._login()
            return await self._request(
                method, path, params=params, json_body=json_body, retry=False,
            )
        raise RuntimeError(f"SEMS+ {path} lỗi (code={code or response.status_code}, msg={message or '-'})")

    async def _ensure_station(self) -> str:
        if self.station_id:
            return self.station_id
        body = await self._request(
            "POST",
            "/sems-plant/api/portal/stations/page",
            json_body={"current": 1, "size": 20},
        )
        rows = ((body.get("data") or {}).get("dataList") or [])
        if not rows or not isinstance(rows[0], dict) or not rows[0].get("id"):
            raise RuntimeError("Không tìm thấy nhà máy trên SEMS+")
        self.station_id = str(rows[0]["id"])
        return self.station_id

    async def _station_row(self) -> dict:
        await self._ensure_station()
        body = await self._request(
            "POST",
            "/sems-plant/api/portal/stations/page",
            json_body={"current": 1, "size": 20},
        )
        for row in (body.get("data") or {}).get("dataList") or []:
            if isinstance(row, dict) and str(row.get("id")) == self.station_id:
                return row
        return {}

    async def _profile(self) -> dict:
        now = time.monotonic()
        if self._station_profile is not None and now - self._profile_at < 3600:
            return self._station_profile
        station_id = await self._ensure_station()
        body = await self._request("GET", f"/sems-plant/api/stations/{station_id}")
        data = body.get("data") or {}
        info = data.get("baseInfo") or {}
        address = data.get("addressInfo") or {}
        self._station_profile = {"info": info, "address": address}
        self._profile_at = now
        return self._station_profile

    async def _inverter(self) -> Optional[str]:
        if self._inverter_sn:
            return self._inverter_sn
        station_id = await self._ensure_station()
        body = await self._request(
            "GET",
            "/sems-plant/api/stations/device/all-status",
            params={"stationId": station_id},
        )
        groups = (body.get("data") or {}).get("deviceDetailList") or []
        for group in groups:
            if not isinstance(group, dict) or group.get("deviceType") != "INVERTER":
                continue
            for status in group.get("statusDetailList") or []:
                detail_map = status.get("detailMap") if isinstance(status, dict) else None
                if isinstance(detail_map, dict) and detail_map:
                    self._inverter_sn = next(iter(detail_map))
                    return self._inverter_sn
        return None

    async def _month_energy(self) -> Optional[float]:
        now = time.monotonic()
        if self._month_kwh is not None and now - self._month_at < 600:
            return self._month_kwh
        serial = await self._inverter()
        if not serial:
            return None
        station_id = await self._ensure_station()
        body = await self._request(
            "GET",
            f"/sems-plant/api/equipments/{serial}/telecounting",
            params={"deviceType": "INVERTER", "pwId": station_id},
        )
        month = _factor(body.get("data"), "proPvStatsMonth")
        if month is not None:
            self._month_kwh = month
            self._month_at = now
        return month

    async def _statistics(self, start: date, end: date) -> list:
        await self._ensure_station()
        body = await self._request(
            "POST",
            "/sems-plant/api/v1/hems/power/statisticsAndPreV2",
            json_body={
                "stationId": self.station_id,
                "items": ["pSystem", "soc", "pBat", "pConsum", "pGrid"],
                "timeScale": 1,
                "timeZone": self._tz_offset,
                "startTime": f"{start.isoformat()} 00:00:00",
                "endTime": f"{end.isoformat()} 23:59:59",
            },
        )
        return (body.get("data") or {}).get("dataList") or []

    async def _energy(self, months: int) -> dict[str, dict[str, float]]:
        now = time.monotonic()
        cached = self._energy_cache.get(months)
        if cached and now - cached[0] < 300:
            return cached[1]
        await self._ensure_station()
        end = datetime.now(VN_TZ).date()
        earliest = end - timedelta(days=max(1, months) * 31)
        cursor = end
        empty_windows = 0
        merged: dict[str, dict[str, float]] = {}
        while cursor >= earliest and empty_windows < 2:
            start = max(earliest, cursor - timedelta(days=WINDOW_DAYS - 1))
            try:
                rows = energy_by_day(await self._statistics(start, cursor))
            except Exception:
                rows = {}
            if any((row.get("pv") or row.get("cons") or row.get("buy")) for row in rows.values()):
                merged.update(rows)
                empty_windows = 0
            else:
                empty_windows += 1
            cursor = start - timedelta(days=1)
            if cursor >= earliest:
                await asyncio.sleep(0.4)
        self._energy_cache[months] = (now, merged)
        return merged

    async def get_metrics(self) -> Metrics:
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_at) < self.min_refresh_s:
            return self._cache
        try:
            metrics = await self._fetch()
            self._cache, self._cache_at = metrics, now
            return metrics
        except Exception as error:
            if self._cache is not None:
                return self._cache
            return Metrics(
                source="cloud",
                status="error",
                station_name=self.station_name or "SEMS+",
                error=f"{type(error).__name__}: {error}",
            )

    async def _fetch(self) -> Metrics:
        station_id = await self._ensure_station()
        flow_body, row, profile = await asyncio.gather(
            self._request(
                "GET",
                "/sems-plant/api/stations/flow",
                params={"stationId": station_id},
            ),
            self._station_row(),
            self._profile(),
        )
        flow = flow_body.get("data")
        if not isinstance(flow, dict) or "pSystem" not in flow:
            raise RuntimeError("SEMS+ không trả power flow")
        today = datetime.now(VN_TZ).date()
        today_rows = energy_by_day(await self._statistics(today, today)).get(today.isoformat(), {})
        try:
            month_energy = await self._month_energy()
        except Exception:
            month_energy = self._month_kwh
        return self._metrics(flow, row, profile, today_rows, month_energy)

    def _metrics(
        self,
        flow: dict,
        row: dict,
        profile: dict,
        today_rows: dict,
        month_energy: Optional[float],
    ) -> Metrics:
        info = profile.get("info") or {}
        address = profile.get("address") or {}
        pv = _watts(_num(flow.get("pSystem"))) or 0
        load = _watts(_num(flow.get("pConsum")))
        grid = _watts(_num(flow.get("pGrid")), flip=True)
        battery = _watts(_num(flow.get("pBat")), flip=True)
        soc = _num(flow.get("soc"))
        produced = _num(row.get("productionToday"))
        if produced is None:
            produced = today_rows.get("pv")
        total = _num(row.get("productionTotal"))
        consumed = today_rows.get("cons")
        bought = today_rows.get("buy")
        sold = today_rows.get("sell")
        price = self.price_per_kwh
        income = round(produced * price) if produced is not None and price else None
        month_income = round(month_energy * price) if month_energy is not None and price else None
        total_income = round(total * price) if total is not None and price else None
        self_use = None
        if consumed:
            self_use = round(max(0.0, consumed - (bought or 0.0)) / consumed, 3)
        capacity = _num(info.get("capacity")) or _num(row.get("pvInstallP")) or self.capacity_kw
        return Metrics(
            source="cloud",
            status="online",
            station_name=self.station_name or row.get("name") or "Home Solar",
            pv_power_w=pv,
            load_power_w=load,
            grid_power_w=grid,
            battery_power_w=battery,
            battery_soc=soc,
            today_energy_kwh=None if produced is None else round(produced, 1),
            total_energy_kwh=None if total is None else round(total, 1),
            today_income=income,
            currency=self.currency,
            capacity_kw=capacity,
            self_use_rate=self_use,
            today_buy_kwh=None if bought is None else round(bought, 1),
            today_sell_kwh=None if sold is None else round(sold, 1),
            today_consumption_kwh=None if consumed is None else round(consumed, 1),
            month_energy_kwh=None if month_energy is None else round(month_energy, 1),
            month_income=month_income,
            total_income=total_income,
            battery_capacity_kwh=_num(info.get("batteryCapacity")),
            battery_reserve_percent=self.battery_reserve_percent,
            lat=_num(address.get("latitude")),
            lon=_num(address.get("longitude")),
        )

    async def fetch_daily_history(self, months: int = 18) -> dict:
        rows = await self._energy(months)
        return {day: round(row["pv"], 1) for day, row in rows.items() if row.get("pv", 0) > 0}

    async def fetch_daily_energy(self, months: int = 18) -> dict:
        rows = await self._energy(months)
        out = {}
        for day, row in rows.items():
            if (row.get("cons") or 0) > 0 or (row.get("buy") or 0) > 0:
                out[day] = {"cons": round(row.get("cons") or 0, 1), "buy": round(row.get("buy") or 0, 1)}
        return out

    async def fetch_day_curve(self, day: str) -> dict:
        now = time.monotonic()
        today = datetime.now(VN_TZ).date().isoformat()
        cached = self._day_cache.get(day)
        if cached and (day != today or (now - cached[0]) < self.min_refresh_s):
            return cached[1]
        parsed = datetime.fromisoformat(day).date()
        data_list = await self._statistics(parsed, parsed)
        points = curve_points(data_list)
        produced = energy_by_day(data_list).get(day, {}).get("pv")
        savings = round(produced * self.price_per_kwh) if produced is not None and self.price_per_kwh else None
        value = {
            "date": day,
            "generation_kwh": None if produced is None else round(produced, 1),
            "savings": savings,
            "currency": self.currency or "VND",
            "points": points,
        }
        self._day_cache[day] = (now, value)
        if len(self._day_cache) > 60:
            oldest = min(self._day_cache, key=lambda key: self._day_cache[key][0])
            self._day_cache.pop(oldest, None)
        return value


def _factor(node, code: str) -> Optional[float]:
    if isinstance(node, dict):
        factors = node.get("factors")
        if isinstance(factors, list):
            for factor in factors:
                if isinstance(factor, dict) and factor.get("code") == code:
                    return _num(factor.get("data"))
        for value in node.values():
            found = _factor(value, code)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _factor(value, code)
            if found is not None:
                return found
    return None
