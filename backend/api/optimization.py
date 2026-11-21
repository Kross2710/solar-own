"""Optimization tab routes: best hours, wasted sun and yield forecast."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.runtime import AppRuntime, get_runtime
from backend.services.curtailment import build_curtailment, marginal_price
from backend.services.day_ahead import build_day_ahead
from backend.services.forecast import build_forecast, build_accuracy


router = APIRouter(prefix="/api", tags=["optimization"])


@router.get("/hourly")
async def hourly(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    """Average 24-hour profile + marginal price, for shifting loads into cheap hours."""
    return JSONResponse({
        "hours": runtime.store.hourly_profile(30),
        "marginal": marginal_price(runtime.store, runtime.tariff, int((runtime.config.get("evn") or {}).get("cycle_start_day", 1))),
        "currency": runtime.config.get("currency") or "VND",
    })


@router.get("/curtailment")
async def curtailment(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    return JSONResponse(await build_curtailment(runtime))


@router.get("/forecast")
async def forecast(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    return JSONResponse(await build_forecast(runtime))


@router.get("/forecast/accuracy")
async def forecast_accuracy(
    model: str | None = Query(default=None, max_length=80),
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    result = await build_accuracy(runtime, model)
    return JSONResponse(result, status_code=404 if result.get("reason") == "unknown_model" else 200)

@router.get("/forecast/day-ahead")
async def day_ahead(runtime: AppRuntime = Depends(get_runtime)) -> JSONResponse:
    return JSONResponse(await build_day_ahead(runtime))
