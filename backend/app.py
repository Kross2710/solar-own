"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.assistant import router as assistant_router
from backend.api.history import router as history_router
from backend.api.metrics import router as metrics_router
from backend.api.optimization import router as optimization_router
from backend.api.system import router as system_router
from backend.runtime import AppRuntime, create_runtime
from backend.services.collector import close_providers, poll_loop
from backend.services.forecast import forecast_loop
from backend.services.notices import notices_loop
from backend.services.sync import evn_loop, sync_loop
from backend.static import NoCacheStaticFiles


def create_app(
    runtime: AppRuntime | None = None,
    *,
    mount_static: bool = True,
) -> FastAPI:
    app_runtime = runtime or create_runtime()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        tasks = [
            asyncio.create_task(poll_loop(app_runtime)),
            asyncio.create_task(sync_loop(app_runtime)),
            asyncio.create_task(evn_loop(app_runtime)),
            asyncio.create_task(forecast_loop(app_runtime)),
            asyncio.create_task(notices_loop(app_runtime)),
        ]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await close_providers(app_runtime)

    application = FastAPI(
        title="Solar Dashboard",
        lifespan=lifespan,
    )
    application.state.runtime = app_runtime

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_origin_regex=(
            r"https?://(localhost|127\.0\.0\.1|\[::1\]|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}"
            r")(:\d+)?"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(metrics_router)
    application.include_router(history_router)
    application.include_router(optimization_router)
    application.include_router(assistant_router)
    application.include_router(system_router)

    web_root = app_runtime.root / "web"
    if mount_static and web_root.exists():
        application.mount(
            "/",
            NoCacheStaticFiles(directory=str(web_root), html=True),
            name="web",
        )

    return application
