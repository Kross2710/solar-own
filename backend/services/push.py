"""Web Push delivery and alert state for the primary inverter feed."""

from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
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
ALERT_TTL = 900
RETRY_DELAYS = (15, 60, 180)
DELIVERY_LEASE = 60
DELIVERY_BATCH = 8
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


@dataclass(frozen=True)
class PushResult:
    status: int
    retry_after: float = 0

    @property
    def retryable(self) -> bool:
        return self.status in (408, 429) or 500 <= self.status < 600


def retry_after_seconds(value: str) -> float:
    try:
        return min(ALERT_TTL, max(0, int(value)))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            return max(0, date.timestamp() - time.time()) if date.tzinfo else 0
        except (ValueError, OverflowError):
            return 0


def alert_topic(event: str) -> str:
    return "inverter" if event.startswith("inverter-") else event


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
                CREATE TABLE IF NOT EXISTS pending_push (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_hash TEXT NOT NULL REFERENCES devices(token_hash) ON DELETE CASCADE,
                    topic TEXT NOT NULL, event TEXT NOT NULL,
                    expires_at REAL NOT NULL, ready_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(token_hash, topic)
                );
            """)

    @contextmanager
    def connection(self):
        database = sqlite3.connect(self.database)
        database.row_factory = sqlite3.Row
        try:
            database.execute("PRAGMA foreign_keys = ON")
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
        previous_battery = self.previous_battery
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
                    stopped_at_floor = (
                        power == 0 and previous_battery is not None
                        and 0 < last_good_at - previous_battery[0] < OUTAGE_SECONDS
                        and previous_battery[1] > BATTERY_FLOOR and previous_battery[2] < 0
                    )
                    if not battery_low and soc <= BATTERY_FLOOR and (
                        (power is not None and power < 0) or stopped_at_floor
                    ):
                        events.append("low-battery")
                        battery_low = True
                    if power is not None:
                        previous_battery = (last_good_at, soc, power)

            if offline != was_offline or battery_low != bool(state["battery_low"]):
                database.execute("UPDATE alert_state SET offline = ?, battery_low = ? WHERE id = 1", (offline, battery_low))
            if state["battery_low"] and not battery_low:
                database.execute("DELETE FROM pending_push WHERE topic = 'low-battery'")
            # Commit each alert and its deliveries together so a restart cannot lose it.
            for event in events:
                database.execute("""
                    INSERT OR REPLACE INTO pending_push (token_hash, topic, event, expires_at, ready_at)
                    SELECT token_hash, ?, ?, ?, ? FROM devices
                """, (alert_topic(event), event, now + ALERT_TTL, now))

        self.previous_battery = previous_battery
        return events

    def claim_deliveries(self, now: float) -> list[sqlite3.Row]:
        with self.connection() as database:
            database.execute("BEGIN IMMEDIATE")
            database.execute("""
                DELETE FROM pending_push
                WHERE expires_at <= ? OR (ready_at <= ? AND attempts > ?)
            """, (now, now, len(RETRY_DELAYS)))
            deliveries = database.execute("""
                SELECT d.*, p.id, p.event, p.topic, p.expires_at, p.attempts + 1 AS attempt
                FROM pending_push p JOIN devices d USING (token_hash)
                WHERE p.ready_at <= ?
                ORDER BY p.ready_at, p.id LIMIT ?
            """, (now, DELIVERY_BATCH)).fetchall()
            database.executemany("""
                UPDATE pending_push SET attempts = ?, ready_at = ? WHERE id = ?
            """, [(job["attempt"], now + DELIVERY_LEASE, job["id"]) for job in deliveries])
            return deliveries

    async def deliver(self, job: sqlite3.Row) -> None:
        attempt = job["attempt"]
        retry_at = None
        ttl = int(job["expires_at"] - time.time())
        if ttl > 0:
            result = await self.send(job, job["event"], ttl=ttl, topic=job["topic"])
            if result.retryable and attempt <= len(RETRY_DELAYS):
                retry_at = time.time() + max(RETRY_DELAYS[attempt - 1], result.retry_after)
        with self.connection() as database:
            if retry_at is not None and retry_at < job["expires_at"]:
                database.execute(
                    "UPDATE pending_push SET ready_at = ? WHERE id = ? AND attempts = ?",
                    (retry_at, job["id"], attempt),
                )
            else:
                database.execute("DELETE FROM pending_push WHERE id = ? AND attempts = ?", (job["id"], attempt))

    async def dispatch(self) -> None:
        deliveries = self.claim_deliveries(time.time())
        await asyncio.gather(*(self.deliver(job) for job in deliveries))

    async def run(self) -> None:
        while True:
            try:
                self.transitions(time.time())
                await self.dispatch()
            except Exception:
                logger.exception("Home Solar alert processing failed")
            await asyncio.sleep(5)

    async def send(self, device: sqlite3.Row, event: str, *, ttl: int = 300, topic: str | None = None) -> PushResult:
        return await asyncio.to_thread(self._send, device, event, ttl, topic)

    def _send(self, device: sqlite3.Row, event: str, ttl: int, topic: str | None) -> PushResult:
        from pywebpush import WebPushException, webpush
        from requests import RequestException, Session

        class NoRedirectSession(Session):
            def post(self, url, **kwargs):
                return super().post(url, allow_redirects=False, **kwargs)

        subscription = json.loads(device["subscription"])
        if not supported_endpoint(subscription["endpoint"]):
            return PushResult(400)

        body = MESSAGES[event][device["language"] == "vi"]
        data = json.dumps({
            "title": "Home Solar", "body": body, "tag": topic or event,
            "path": "/settings" if event == "test" else "/",
        })
        try:
            with NoRedirectSession() as session:
                response = webpush(
                    subscription, data,
                    vapid_private_key=self.vapid, vapid_claims={"sub": self.contact},
                    ttl=ttl, timeout=8, requests_session=session,
                    headers={"Topic": topic} if topic else None,
                )
        except WebPushException as error:
            response = error.response
            if response is None:
                logger.warning("Could not package Web Push message for %s", event)
                return PushResult(400)
        except RequestException as error:
            logger.warning("Web Push request failed for %s (%s)", event, type(error).__name__)
            return PushResult(503)
        except ValueError:
            logger.warning("Invalid Web Push data for %s", event)
            return PushResult(400)

        status = response.status_code
        if 200 <= status < 300:
            return PushResult(204)
        if status in (404, 410):
            with self.connection() as database:
                database.execute(
                    "DELETE FROM devices WHERE token_hash = ? AND subscription = ?",
                    (device["token_hash"], device["subscription"]),
                )
            return PushResult(410)

        logger.warning("Web Push service rejected %s (status %s)", event, status)
        return PushResult(status, retry_after_seconds(response.headers.get("Retry-After", "")))
