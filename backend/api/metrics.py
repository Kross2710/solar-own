"""Realtime metric routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.runtime import AppRuntime, get_runtime
from backend.services.collector import snapshot


router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
async def metrics(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    latest = runtime.latest
    if latest is None:
        try:
            latest = await snapshot(runtime)
        except Exception as error:
            latest = {
                "source": runtime.config.get("source", "mock"),
                "status": "error",
                "error": f"{type(error).__name__}: {error}",
                "pv_power_w": 0,
                "poll_interval_seconds": runtime.poll_interval,
            }
    return JSONResponse(latest)
