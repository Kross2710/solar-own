"""Historical metric and aggregation routes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend import config
from backend.runtime import AppRuntime, get_runtime
from backend.services.history_summary import build_summary
from providers.base import VN_TZ


router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
async def history(
    hours: int = 12,
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    return JSONResponse(runtime.store.recent(hours))


@router.get("/daily")
async def daily(
    days: int = 30,
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    return JSONResponse(runtime.store.daily_full(days))


@router.get("/day")
async def day(
    date: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    fetch_day_curve = getattr(runtime.history_provider, "fetch_day_curve", None)
    if not callable(fetch_day_curve):
        return JSONResponse(
            {"error": "not_supported", "date": date, "points": []}
        )

    try:
        fetch = cast(
            Callable[[str], Awaitable[dict[str, Any]]],
            fetch_day_curve,
        )
        return JSONResponse(await fetch(date))
    except Exception as error:
        return JSONResponse(
            {
                "error": f"{type(error).__name__}: {error}",
                "date": date,
                "points": [],
            }
        )


@router.get("/summary")
async def summary(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    return JSONResponse(
        build_summary(
            runtime.store,
            runtime.tariff,
            runtime.config.get("currency") or "VND",
        )
    )

# WIP
# @router.get("/hourly")
# async def hourly(
#     runtime: AppRuntime = Depends(get_runtime),
# ) -> JSONResponse:
#     """Hồ sơ 24 giờ TB + giá biên — cho "giờ vàng dịch tải" (#9)."""

#     monthly_buy = sum((r.get("buy", 0) for r in runtime.store.daily_full(35)[-30:]))
#     return JSONResponse({
#         "hours": runtime.store.hourly_profile(30),
#         "marginal": round(runtime.tariff.marginal(monthly_buy or 235)),
#         "currency": runtime.config.get("currency") or "VND",
#     })
    
# NEED ML FIRST TO PREDICT BASED ON WEATHER + USAGE + TARIFF
# @router.get("/money")
# async def money(
#     runtime: AppRuntime = Depends(get_runtime),
# ) -> JSONResponse:
#     """Tiền điện theo bậc thang EVN: tiết kiệm + hoá đơn dự kiến + hoá đơn EVN THẬT (kỳ đã chốt)."""
#     today = datetime.now(VN_TZ).date() # type: ignore
    
# @router.get("/evn")
# async def evn(
#     runtime: AppRuntime = Depends(get_runtime),
# ) -> JSONResponse:
#     """Ground-truth EVN CSKH: hoá đơn tiền điện THẬT + đối chiếu kWh công tơ vs ước tính dashboard.

#     Công khai (mở từ Cài đặt > Kỹ thuật). KHÔNG chứa PII — chỉ kWh/chỉ số/tiền/ngày trả.
#     `compare` so kWh-mua công tơ EVN (evn_daily) với daily.buy (ước tính SEMS) theo tháng = QA dữ liệu.
#     """    
#     bills = runtime.store.evn_bills_all()
#     daily = runtime.store.evn_daily_all()
#     if not bills or not daily:
#         return JSONResponse({"error": "no_data", "bills": [], "daily": []})
#     evn_m: dict = {}
#     for r in daily:
#         if r.get("kwh") is not None:
#             mk = r["day"][:7] # YYYY-MM
#             evn_m[mk] = evn_m.get(mk, 0.0) + r["kwh"]
#     dash_m = {r["month"]: r.get("buy") for r in runtime.store.monthly(60)}
#     compare = []
#     for mk in sorted(evn_m):
#         ev = evn_m[mk]
#         db = dash_m.get(mk)
#         compare.append({
#             "month": mk,
#             "evn_kwh": round(ev, 1),
#             "dash_buy": round(db, 1) if db is not None else None,
#             "diff_pct": round((ev - db) / ev * 100, 1) if db is not None else None,
#         })
#     last = daily[-1] if daily else {}
#     return JSONResponse({
#         "ready": True,
#         "currency": runtime.config.get("currency") or "VND",
#         "meter_index": last.get("meter_index"),
#         "last_day": last.get("day"),
#         "bills": bills,        # [{cycle,kwh,amount,paid_date}] cũ->mới
#         "compare": compare,    # [{month,evn_kwh,dash_buy,diff_pct}] cũ->mới
#     })
    
# @router.get("/api/health")
# async def health():
#     live = state.get("latest") or {}
#     return {
#         "ok": True,
#         "source": runtime.config.get("source"),
#         "live_provider": live_provider.name,
#         "history_provider": history_provider.name,
#         "dual": history_provider is not live_provider,
#         "live_status": live.get("status"),
#         "live_source": live.get("source"),
#     }