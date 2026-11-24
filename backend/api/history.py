"""Historical metric and aggregation routes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
import logging
from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.runtime import AppRuntime, get_runtime
from backend.services.history_summary import build_summary
from backend.services.money import build_money
from providers.base import VN_TZ

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
async def history(
    hours: int = Query(12, ge=1, le=1000),
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    return JSONResponse(runtime.store.recent(hours))


@router.get("/daily")
async def daily(
    days: int = Query(30, ge=1, le=1000),
    include_unused_solar: bool = False,
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    if include_unused_solar:
        return JSONResponse(runtime.store.daily_full(days, include_unused_solar=True))
    return JSONResponse(runtime.store.daily_full(days))


@router.get("/day")
async def day(
    date: datetime.date = Query(...),
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    fetch_day_curve = getattr(runtime.history_provider, "fetch_day_curve", None)
    if not callable(fetch_day_curve):
        return JSONResponse(
            {"error": "not_supported", "date": date.isoformat(), "points": []}
        )

    iso = date.isoformat()
    try:
        fetch = cast(
            Callable[[str], Awaitable[dict[str, Any]]],
            fetch_day_curve,
        )
        return JSONResponse(await fetch(iso))
    except Exception:
        # Genuine provider failure: log server-side, return only a generic code.
        # Never echo the exception type/message (they can leak internals + caller input).
        logger.error("fetch_day_curve failed for %s", iso, exc_info=True)
        return JSONResponse({"error": "fetch_failed", "date": iso, "points": []})


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

@router.get("/money")
async def money(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    """EVN tiered savings + projected bill + the real EVN bill of the last closed cycle."""
    return JSONResponse(build_money(runtime, datetime.datetime.now(VN_TZ).date()))


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