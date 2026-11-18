"""Settings sheet: system status, manual sync and the CSV export."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from backend.runtime import AppRuntime, get_runtime
from backend.services.sync import sync_once
from providers.base import VN_TZ


router = APIRouter(prefix="/api", tags=["system"])

# SEMS rate-limits aggressively; a manual sync right after another one adds nothing.
MANUAL_SYNC_GAP_SECONDS = 120

_background: set[asyncio.Task] = set()


def _seconds_since(iso: str | None) -> float | None:
    if not iso:
        return None
    return (datetime.now(VN_TZ) - datetime.fromisoformat(iso)).total_seconds()


@router.get("/status")
async def status(runtime: AppRuntime = Depends(get_runtime)) -> JSONResponse:
    store = runtime.store
    rows = store.daily_full(4000)
    evn_days = store.evn_daily_all()
    forecaster = runtime.forecaster
    quality: dict[str, Any] = forecaster.quality if forecaster.ready else {}

    return JSONResponse({
        "source": runtime.config.get("source") or "mock",
        "live": (runtime.latest or {}).get("status"),
        "history": {
            "days": len(rows),
            "first_day": rows[0]["day"] if rows else None,
            "last_day": rows[-1]["day"] if rows else None,
        },
        "sync": {
            "running": runtime.sync_lock.locked(),
            "last": runtime.last_sync,
            "supported": callable(getattr(runtime.history_provider, "fetch_daily_history", None)),
        },
        "evn": {
            "enabled": bool(((runtime.config.get("evn") or {}).get("portal") or {}).get("enabled")),
            "last_day": evn_days[-1]["day"] if evn_days else None,
            "bills": store.evn_counts()["bills"],
        },
        "forecast": {
            "ready": forecaster.ready,
            "model": forecaster.model_name if forecaster.ready else None,
            "mae_kwh": quality.get("mae"),
            "n_train": quality.get("n_train"),
            "updated_at": forecaster.updated_at if forecaster.ready else None,
        },
        "assistant": bool(runtime.assistant and runtime.assistant.chat_enabled),
        "battery_reserve_percent": runtime.config.get("battery_reserve_percent", 20),
    })


@router.post("/sync")
async def sync_now(runtime: AppRuntime = Depends(get_runtime)) -> JSONResponse:
    """Start a sync pass in the background; the UI polls /api/status for the result."""
    if runtime.sync_lock.locked():
        return JSONResponse({"ok": False, "reason": "running"}, status_code=409)
    since = _seconds_since((runtime.last_sync or {}).get("finished_at"))
    if since is not None and since < MANUAL_SYNC_GAP_SECONDS:
        return JSONResponse(
            {"ok": False, "reason": "too_soon", "retry_in": round(MANUAL_SYNC_GAP_SECONDS - since)},
            status_code=429,
        )
    task = asyncio.create_task(sync_once(runtime))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return JSONResponse({"ok": True})


@router.get("/export.csv")
async def export_csv(runtime: AppRuntime = Depends(get_runtime)) -> Response:
    """The whole `daily` table (it is never pruned): generation, consumption, grid purchase."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["day", "generation_kwh", "consumption_kwh", "grid_buy_kwh"])
    for row in runtime.store.daily_full(4000):
        writer.writerow([row["day"], row.get("kwh"), row.get("cons"), row.get("buy")])
    today = datetime.now(VN_TZ).date().isoformat()
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="solar-daily-{today}.csv"'},
    )
