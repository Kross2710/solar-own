"""Device registration and test delivery for Home Solar Web Push."""

from __future__ import annotations

import asyncio
import base64
import hmac
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

from backend.runtime import AppRuntime, get_runtime
from backend.services.push import PushAlerts, TEST_INTERVAL, supported_endpoint

router = APIRouter(prefix="/api/push", tags=["push"])
Runtime = Annotated[AppRuntime, Depends(get_runtime)]
Language = Literal["en", "vi"]


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=87, max_length=88)
    auth: str = Field(min_length=22, max_length=24)


class Subscription(BaseModel):
    endpoint: str = Field(max_length=2048)
    keys: SubscriptionKeys


class Enrollment(BaseModel):
    code: str = Field(max_length=256)
    subscription: Subscription
    language: Language


class DevicePreferences(BaseModel):
    language: Language


def device_token(authorization: Annotated[str, Header(max_length=100)] = "") -> str:
    if not re.fullmatch(r"Bearer [a-zA-Z0-9_-]{32,64}", authorization):
        raise HTTPException(401)
    return authorization.removeprefix("Bearer ")


Token = Annotated[str, Depends(device_token)]


def service(runtime: AppRuntime) -> PushAlerts:
    if runtime.push_alerts is None:
        raise HTTPException(503)
    return runtime.push_alerts


def decode_key(value: str) -> bytes:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+={0,2}", value):
        raise ValueError("Invalid key encoding")
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def validate_subscription(subscription: Subscription) -> None:
    from cryptography.hazmat.primitives.asymmetric import ec

    if not supported_endpoint(subscription.endpoint):
        raise HTTPException(422, "Unsupported push service")
    try:
        public_key = decode_key(subscription.keys.p256dh)
        if len(public_key) != 65 or len(decode_key(subscription.keys.auth)) != 16:
            raise ValueError("Invalid subscription key size")
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public_key)
    except ValueError:
        raise HTTPException(422, "Invalid subscription keys") from None


@router.get("/config")
def configuration(runtime: Runtime, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    alerts = runtime.push_alerts
    return {"enabled": alerts is not None, "publicKey": alerts.public_key if alerts else None}


@router.get("/device")
def get_device(runtime: Runtime, token: Token, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    device = service(runtime).device(token)
    return {"endpoint": device["endpoint"], "language": device["language"]} if device else {"endpoint": None}


@router.put("/device", status_code=204)
def enroll_device(enrollment: Enrollment, runtime: Runtime, token: Token) -> Response:
    alerts = service(runtime)
    if not hmac.compare_digest(enrollment.code.encode(), alerts.setup_code.encode()):
        raise HTTPException(403)
    validate_subscription(enrollment.subscription)
    alerts.enroll(token, enrollment.subscription.model_dump(), enrollment.language)
    return Response(status_code=204)


@router.patch("/device", status_code=204)
def update_device(prefs: DevicePreferences, runtime: Runtime, token: Token) -> Response:
    service(runtime).update_language(token, prefs.language)
    return Response(status_code=204)


@router.delete("/device", status_code=204)
def delete_device(runtime: Runtime, token: Token) -> Response:
    service(runtime).remove(token)
    return Response(status_code=204)


@router.post("/test", status_code=204)
async def test_device(runtime: Runtime, token: Token) -> Response:
    alerts = service(runtime)
    status, device = await asyncio.to_thread(alerts.reserve_test, token)
    if device is None:
        headers = {"Retry-After": str(TEST_INTERVAL)} if status == 429 else None
        raise HTTPException(status, headers=headers)
    result = await alerts.send(device, "test")
    status = result.status if result.status in (204, 410) else 502
    return Response(status_code=status)
