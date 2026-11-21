"""Web Push delivery and alert state for the primary inverter feed."""

from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit

from providers.base import VN_TZ

logger = logging.getLogger(__name__)
OUTAGE_SECONDS = 600
BATTERY_FLOOR = 20
BATTERY_REARM = 22
TEST_INTERVAL = 60
MESSAGES = {
    "low-battery": (
        "The battery reached its 20% reserve.",
        "Pin đã chạm ngưỡng dự phòng 20%.",
    ),
    "inverter-offline": (
        "No new data from the primary inverter feed for 10 minutes.",
        "Đã 10 phút chưa có dữ liệu mới từ nguồn inverter chính.",
    ),
    "inverter-online": (
        "The primary inverter feed is back online.",
        "Nguồn dữ liệu inverter chính đã hoạt động trở lại.",
    ),
    "test": (
        "This device can receive Home Solar alerts.",
        "Thiết bị này có thể nhận cảnh báo từ Home Solar.",
    ),
}


def supported_endpoint(endpoint: str) -> bool:
    try:
        if any(character.isspace() or character == "\\" or ord(character) < 33 for character in endpoint):
            return False
        url = urlsplit(endpoint)
        host = url.hostname or ""
    except ValueError:
        return False
    if url.scheme != "https" or url.netloc != host or url.fragment or not url.path:
        return False
    if host == "web.push.apple.com" or host.endswith(".push.apple.com"):
        return True
    return host == "fcm.googleapis.com" and url.path.startswith("/fcm/send/")


class PushAlerts:
    def __init__(self, root: Path, config: dict) -> None:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from py_vapid import Vapid

        key_path = root / config["private_key_file"]
        self.vapid = Vapid.from_pem(key_path.read_bytes())
        public_bytes = self.vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        self.public_key = base64.urlsafe_b64encode(public_bytes).decode().rstrip("=")
        self.contact = config["contact"]
        self.setup_code = config["setup_code"]
        if len(self.setup_code) < 24 or not (self.contact.startswith("mailto:") and "@" in self.contact):
            raise ValueError("Web Push requires a random setup code and a mailto: contact")

        self.database = root / "push.db"
        self.started_at = time.time()
        self.last_good_at: float | None = None
        self.reading: dict | None = None
        self.previous_battery: tuple[float, float, float] | None = None
        with self.connection() as database:
            database.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    token_hash TEXT PRIMARY KEY, endpoint TEXT NOT NULL UNIQUE,
                    subscription TEXT NOT NULL, language TEXT NOT NULL, last_test REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS alert_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    offline INTEGER NOT NULL, battery_low INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO alert_state VALUES (1, 0, 0);
            """)

    @contextmanager
    def connection(self):
        database = sqlite3.connect(self.database)
        database.row_factory = sqlite3.Row
        try:
            with database:
                yield database
        finally:
            database.close()

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def enroll(self, token: str, subscription: dict, language: str) -> None:
        endpoint = subscription["endpoint"]
        token_hash = self.token_hash(token)
        with self.connection() as database:
            database.execute("DELETE FROM devices WHERE endpoint = ? AND token_hash != ?", (endpoint, token_hash))
            database.execute("""
                INSERT INTO devices (token_hash, endpoint, subscription, language) VALUES (?, ?, ?, ?)
                ON CONFLICT(token_hash) DO UPDATE SET
                    endpoint = excluded.endpoint, subscription = excluded.subscription, language = excluded.language
            """, (token_hash, endpoint, json.dumps(subscription), language))

    def device(self, token: str):
        with self.connection() as database:
            return database.execute("SELECT * FROM devices WHERE token_hash = ?", (self.token_hash(token),)).fetchone()

    def update_language(self, token: str, language: str) -> None:
        with self.connection() as database:
            database.execute("UPDATE devices SET language = ? WHERE token_hash = ?", (language, self.token_hash(token)))

    def remove(self, token: str) -> None:
        with self.connection() as database:
            database.execute("DELETE FROM devices WHERE token_hash = ?", (self.token_hash(token),))

    def reserve_test(self, token: str):
        with self.connection() as database:
            now = time.time()
            database.execute("BEGIN IMMEDIATE")
            device = database.execute("SELECT * FROM devices WHERE token_hash = ?", (self.token_hash(token),)).fetchone()
            if device is None:
                return 404, None
            if now - device["last_test"] < TEST_INTERVAL:
                return 429, None
            database.execute("UPDATE devices SET last_test = ? WHERE token_hash = ?", (now, device["token_hash"]))
            return 200, device

    def observe(self, metrics: dict) -> None:
        self.reading = metrics
        if metrics["status"] == "online" and metrics["source"] != "mock":
            try:
                timestamp = datetime.fromisoformat(metrics["timestamp"])
            except (TypeError, ValueError):
                self.reading = None
                return
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=VN_TZ)
            # SEMS can keep returning its last cached reading when a refresh fails.
            self.last_good_at = min(timestamp.timestamp(), time.time())

    def transitions(self, now: float) -> list[str]:
        events = []
        with self.connection() as database:
            database.execute("BEGIN IMMEDIATE")
            state = database.execute("SELECT offline, battery_low FROM alert_state WHERE id = 1").fetchone()
            was_offline = bool(state["offline"])
            last_good_at = self.last_good_at
            offline = (
                now - (last_good_at if last_good_at is not None else self.started_at) >= OUTAGE_SECONDS
                or (last_good_at is None and was_offline)
            )
            battery_low = bool(state["battery_low"])
            if offline != was_offline:
                events.append("inverter-offline" if offline else "inverter-online")

            reading = self.reading
            if not offline and last_good_at is not None and reading and reading["status"] == "online" and reading["source"] != "mock":
                soc, power = reading.get("battery_soc"), reading.get("battery_power_w")
                if soc is not None and 0 <= soc <= 100:
                    if soc >= BATTERY_REARM:
                        battery_low = False
                    previous = self.previous_battery
                    stopped_at_floor = (
                        power == 0 and previous is not None
                        and 0 < last_good_at - previous[0] < OUTAGE_SECONDS
                        and previous[1] > BATTERY_FLOOR and previous[2] < 0
                    )
                    if not battery_low and soc <= BATTERY_FLOOR and (
                        (power is not None and power < 0) or stopped_at_floor
                    ):
                        events.append("low-battery")
                        battery_low = True
                    if power is not None:
                        self.previous_battery = (last_good_at, soc, power)

            if offline != was_offline or battery_low != bool(state["battery_low"]):
                database.execute("UPDATE alert_state SET offline = ?, battery_low = ? WHERE id = 1", (offline, battery_low))

        return events

    async def run(self) -> None:
        while True:
            try:
                for event in self.transitions(time.time()):
                    with self.connection() as database:
                        devices = database.execute("SELECT * FROM devices").fetchall()
                    # Bound concurrent egress without tying up telemetry collection.
                    for start in range(0, len(devices), 8):
                        await asyncio.gather(*(self.send(device, event) for device in devices[start:start + 8]))
            except Exception:
                logger.exception("Home Solar alert processing failed")
            await asyncio.sleep(5)

    async def send(self, device, event: str) -> int:
        return await asyncio.to_thread(self._send, device, event)

    def _send(self, device, event: str) -> int:
        from pywebpush import WebPushException, webpush
        from requests import RequestException, Session

        class NoRedirectSession(Session):
            def post(self, url, **kwargs):
                return super().post(url, allow_redirects=False, **kwargs)

        subscription = json.loads(device["subscription"])
        if not supported_endpoint(subscription["endpoint"]):
            return 502

        body = MESSAGES[event][device["language"] == "vi"]
        data = json.dumps({
            "title": "Home Solar", "body": body, "tag": event,
            "path": "/settings" if event == "test" else "/",
        })
        try:
            with NoRedirectSession() as session:
                response = webpush(
                    subscription, data,
                    vapid_private_key=self.vapid, vapid_claims={"sub": self.contact},
                    ttl=300 if event == "test" else 900, timeout=8, requests_session=session,
                )
            return 204 if 200 <= response.status_code < 300 else 502
        except WebPushException as error:
            status = error.response.status_code if error.response is not None else None
            if status in (404, 410):
                with self.connection() as database:
                    database.execute(
                        "DELETE FROM devices WHERE token_hash = ? AND subscription = ?",
                        (device["token_hash"], device["subscription"]),
                    )
                return 410
            logger.warning("Web Push service rejected %s (status %s)", event, status)
        except (RequestException, ValueError) as error:
            logger.warning("Web Push delivery failed for %s (%s)", event, type(error).__name__)
        return 502
