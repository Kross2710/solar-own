"""Realtime metric routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.runtime import AppRuntime, get_runtime
from backend.services.collector import snapshot

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
async def metrics(
    runtime: AppRuntime = Depends(get_runtime),
) -> JSONResponse:
    latest = runtime.latest
    if latest is None:
        try:
            latest = await snapshot(runtime)
        except Exception:
            # Genuine snapshot failure: log server-side, return only a generic code.
            # Never echo the exception type/message (leaks internals to callers).
            logger.error("snapshot failed", exc_info=True)
            latest = {
                "source": runtime.config.get("source", "mock"),
                "status": "error",
                "error": "snapshot_failed",
                "pv_power_w": 0,
                "poll_interval_seconds": runtime.poll_interval,
            }
    return JSONResponse(latest)
