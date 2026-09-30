"""Optimization tab routes: best hours, wasted sun and yield forecast."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.runtime import AppRuntime, get_runtime
from backend.services.curtailment import build_curtailment, marginal_price
from backend.services.forecast import build_forecast


router = APIRouter(prefix="/api", tags=["optimization"])


@router.get("/hourly")
async def hourly(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    """Average 24-hour profile + marginal price, for shifting loads into cheap hours."""
    return JSONResponse({
        "hours": runtime.store.hourly_profile(30),
        "marginal": marginal_price(runtime.store, runtime.tariff),
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
