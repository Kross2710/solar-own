"""Assistant chat (SSE), user-confirmed actions and proactive notices."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.runtime import AppRuntime, get_runtime
from backend.services.assistant import apply_action, build_context, build_tools
from backend.services.notices import active_notices
from providers.base import VN_TZ


router = APIRouter(prefix="/api", tags=["assistant"])

# Keeps the Gemini quota safe: few concurrent chats, and a short gap between turns.
MAX_CONCURRENT_CHATS = 2
MIN_SECONDS_BETWEEN_TURNS = 1.2
# The assistant trims further (12 turns, 2000 chars each).
MAX_MESSAGES = 30

_chat_slots = asyncio.Semaphore(MAX_CONCURRENT_CHATS)
_last_turn: dict[str, datetime | None] = {"at": None}


def _chat_enabled(runtime: AppRuntime) -> bool:
    return bool(runtime.assistant and runtime.assistant.chat_enabled)


@router.get("/ai_status")
async def ai_status(runtime: AppRuntime = Depends(get_runtime)) -> JSONResponse:
    return JSONResponse({"enabled": _chat_enabled(runtime)})


@router.post("/chat")
async def chat(request: Request, runtime: AppRuntime = Depends(get_runtime)):
    """Multi-turn chat. Body {messages: [{role, content}], lang}. Streams SSE events:
    status (a tool is being called), delta (text), error, done (with proposed actions)."""
    assistant = runtime.assistant
    if assistant is None or not assistant.chat_enabled:
        return JSONResponse({"enabled": False})

    now = datetime.now(VN_TZ)
    last = _last_turn["at"]
    if last and (now - last).total_seconds() < MIN_SECONDS_BETWEEN_TURNS:
        return JSONResponse({"enabled": True, "error_code": "rate_limit"}, status_code=429)
    _last_turn["at"] = now

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body if isinstance(body, dict) else {}
    messages = body.get("messages")
    messages = messages[-MAX_MESSAGES:] if isinstance(messages, list) else []
    lang = "vi" if body.get("lang") == "vi" else "en"

    actions: list[dict[str, Any]] = []
    tools = build_tools(runtime, actions)
    context = build_context(runtime)

    async def events() -> AsyncIterator[str]:
        def event(payload: dict[str, Any]) -> str:
            return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

        try:
            async with _chat_slots:
                async for item in assistant.chat_stream(context, messages, lang=lang, tools=tools):
                    yield event(item)
            yield event({"type": "done", "actions": actions})
        except Exception as error:
            # Never send upstream details to the browser (they may include the request).
            print(f"  [chat] stream error: {type(error).__name__}: {error}", flush=True)
            yield event({"type": "error", "error_code": "assistant_error"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/action")
async def action(request: Request, runtime: AppRuntime = Depends(get_runtime)) -> JSONResponse:
    """Apply an assistant suggestion after the user pressed "Apply". Body {kind, params}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body if isinstance(body, dict) else {}
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    try:
        return JSONResponse(apply_action(runtime, str(body.get("kind") or ""), params))
    except ValueError as error:
        return JSONResponse({"ok": False, "error_code": str(error)}, status_code=400)
    except Exception as error:
        print(f"  [action] error: {type(error).__name__}: {error}", flush=True)
        return JSONResponse({"ok": False, "error_code": "action_error"}, status_code=500)


@router.get("/notices")
async def notices(runtime: AppRuntime = Depends(get_runtime)) -> JSONResponse:
    return JSONResponse({"notices": active_notices(runtime)})


@router.post("/notices/{notice_id}/dismiss")
async def dismiss_notice(notice_id: int, runtime: AppRuntime = Depends(get_runtime)) -> JSONResponse:
    return JSONResponse({"ok": runtime.store.notice_dismiss(notice_id)})
