import asyncio
from base64 import urlsafe_b64encode
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import AsyncMock, call, patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.runtime import create_runtime
from backend.services.push import (
    ALERT_TTL, OUTAGE_SECONDS, RETRY_DELAYS, PushAlerts, PushResult, supported_endpoint,
)


def encode(data: bytes) -> str:
    return urlsafe_b64encode(data).decode().rstrip("=")


@skipUnless(find_spec("pywebpush"), "optional pywebpush dependency")
class PushTests(TestCase):
    def setUp(self):
        from py_vapid import Vapid

        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        vapid = Vapid()
        vapid.generate_keys()
        vapid.save_key(self.root / "private.pem")
        self.config = {
            "private_key_file": "private.pem",
            "contact": "mailto:test@example.com",
            "setup_code": "pairing-code-for-tests-only",
        }
        self.alerts = PushAlerts(self.root, self.config)
        self.now = self.alerts.started_at

    def observe(self, *, seconds=0, soc=75, power=-300, status="online"):
        timestamp = self.now + seconds
        with patch("backend.services.push.time.time", return_value=timestamp):
            self.alerts.observe({
                "source": "local",
                "status": status,
                "timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                "battery_soc": soc,
                "battery_power_w": power,
            })
        return self.alerts.transitions(timestamp)

    def test_reserve_crossing_rearms_and_survives_restart(self):
        self.assertEqual(self.observe(soc=21), [])
        self.assertEqual(self.observe(seconds=5, soc=20, power=0), ["low-battery"])
        self.assertEqual(self.observe(seconds=10, soc=19), [])
        self.alerts = PushAlerts(self.root, self.config)
        self.assertEqual(self.observe(seconds=15, soc=19), [])
        self.assertEqual(self.observe(seconds=20, soc=21), [])
        self.assertEqual(self.observe(seconds=25, soc=22), [])
        self.assertEqual(self.observe(seconds=30, soc=19, power=200), [])
        self.assertEqual(self.observe(seconds=35, soc=19), ["low-battery"])

    def test_stale_primary_data_and_recovery(self):
        self.assertEqual(self.observe(), [])
        self.assertEqual(self.observe(seconds=20, status="offline"), [])
        self.assertEqual(self.alerts.transitions(self.now + OUTAGE_SECONDS - 1), [])
        self.assertEqual(self.alerts.transitions(self.now + OUTAGE_SECONDS), ["inverter-offline"])
        self.assertEqual(self.alerts.transitions(self.now + OUTAGE_SECONDS + 5), [])
        self.alerts = PushAlerts(self.root, self.config)
        self.assertEqual(self.alerts.transitions(self.alerts.started_at + 5), [])
        self.assertEqual(self.observe(seconds=OUTAGE_SECONDS + 10), ["inverter-online"])

    def dispatch_at(self, now, send):
        with patch("backend.services.push.time.time", return_value=now), patch.object(self.alerts, "send", send):
            asyncio.run(self.alerts.dispatch())

    def enroll(self, token):
        self.alerts.enroll(token, {"endpoint": f"https://web.push.apple.com/{token}"}, "en")

    def test_retries_survive_restart_and_only_target_failed_devices(self):
        self.enroll("first")
        self.enroll("second")
        now = self.now + OUTAGE_SECONDS
        self.assertEqual(self.alerts.transitions(now), ["inverter-offline"])

        async def send_result(job, event, **kwargs):
            if job["endpoint"].endswith("/first"):
                return PushResult(204)
            return PushResult(429, retry_after=45)

        send = AsyncMock(side_effect=send_result)
        self.dispatch_at(now, send)
        self.assertEqual({args.args[0]["attempt"] for args in send.await_args_list}, {1})
        self.assertEqual(send.await_count, 2)

        self.alerts = PushAlerts(self.root, self.config)
        self.assertEqual(self.alerts.transitions(now + 5), [])
        retry = AsyncMock(return_value=PushResult(204))
        self.dispatch_at(now + 44, retry)
        retry.assert_not_awaited()
        self.dispatch_at(now + 45, retry)
        retry.assert_awaited_once()
        job = retry.await_args.args[0]
        self.assertTrue(job["endpoint"].endswith("/second"))
        self.assertEqual(job["attempt"], 2)
        self.assertEqual(retry.await_args, call(job, "inverter-offline", ttl=ALERT_TTL - 45, topic="inverter"))
        self.dispatch_at(now + 300, retry)
        self.assertEqual(retry.await_count, 1)

    def test_transient_failures_stop_after_the_retry_budget(self):
        self.enroll("timeout")
        now = self.now + OUTAGE_SECONDS
        self.alerts.transitions(now)

        send = AsyncMock(return_value=PushResult(503))
        self.dispatch_at(now, send)
        for delay in RETRY_DELAYS:
            now += delay
            self.dispatch_at(now - 1, send)
            self.dispatch_at(now, send)
        self.dispatch_at(now + 60, send)
        self.assertEqual(send.await_count, 1 + len(RETRY_DELAYS))
        with self.alerts.connection() as database:
            self.assertEqual(database.execute("SELECT COUNT(*) FROM pending_push").fetchone()[0], 0)

    def test_recovery_supersedes_a_pending_outage_and_lease_prevents_double_claim(self):
        self.enroll("device")
        now = self.now + OUTAGE_SECONDS
        self.alerts.transitions(now)
        self.assertEqual([job["event"] for job in self.alerts.claim_deliveries(now)], ["inverter-offline"])
        other = PushAlerts(self.root, self.config)
        self.assertEqual(other.claim_deliveries(now + 1), [])
        self.assertEqual(self.observe(seconds=OUTAGE_SECONDS + 5), ["inverter-online"])

        send = AsyncMock(return_value=PushResult(403))
        self.dispatch_at(now + 5, send)
        send.assert_awaited_once()
        self.assertEqual(send.await_args.args[1], "inverter-online")
        self.dispatch_at(now + 75, send)
        self.assertEqual(send.await_count, 1)

    def test_disabled_devices_and_expired_deliveries_are_discarded(self):
        self.enroll("disabled")
        self.enroll("expired")
        now = self.now + OUTAGE_SECONDS
        self.alerts.transitions(now)
        self.alerts.remove("disabled")
        with self.alerts.connection() as database:
            self.assertEqual(database.execute("SELECT COUNT(*) FROM pending_push").fetchone()[0], 1)
        send = AsyncMock()
        self.dispatch_at(now + ALERT_TTL, send)
        send.assert_not_awaited()
        with self.alerts.connection() as database:
            self.assertEqual(database.execute("SELECT COUNT(*) FROM pending_push").fetchone()[0], 0)

    def test_enrollment_test_delivery_and_retirement(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from requests import Response, Timeout

        runtime = create_runtime({"source": "mock"}, self.root)
        runtime.push_alerts = self.alerts
        client = TestClient(create_app(runtime, mount_static=False))
        self.addCleanup(client.close)
        endpoint = "https://web.push.apple.com/test-subscription"
        public_key = ec.generate_private_key(ec.SECP256R1()).public_key()
        subscription = {
            "endpoint": endpoint,
            "keys": {
                "p256dh": encode(public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)),
                "auth": encode(bytes(16)),
            },
        }
        enrollment = {"code": self.config["setup_code"], "subscription": subscription, "language": "vi"}
        auth = {"Authorization": "Bearer " + "a" * 36}

        config = client.get("/api/push/config")
        self.assertEqual(config.json(), {"enabled": True, "publicKey": self.alerts.public_key})
        self.assertEqual(config.headers["cache-control"], "no-store")
        self.assertEqual(client.put("/api/push/device", json=enrollment).status_code, 401)
        self.assertEqual(client.put("/api/push/device", json={**enrollment, "code": "wrong"}, headers=auth).status_code, 403)
        self.assertEqual(client.put("/api/push/device", json=enrollment, headers=auth).status_code, 204)
        self.assertEqual(client.get("/api/push/device", headers=auth).json(), {"endpoint": endpoint, "language": "vi"})

        response = Response()
        response.status_code = 201
        with patch("requests.Session.post", return_value=response) as post:
            self.assertEqual(client.post("/api/push/test", headers=auth).status_code, 204)
            self.assertEqual(client.post("/api/push/test", headers=auth).status_code, 429)
        post.assert_called_once()
        request = post.call_args.kwargs
        self.assertFalse(request["allow_redirects"])
        self.assertEqual(request["headers"]["content-encoding"], "aes128gcm")
        self.assertTrue(request["headers"]["authorization"].startswith("vapid "))
        self.assertNotIn(b"Home Solar", request["data"])

        device = self.alerts.device("a" * 36)
        with patch("requests.Session.post", side_effect=Timeout):
            result = asyncio.run(self.alerts.send(device, "inverter-offline", ttl=600, topic="inverter"))
        self.assertEqual(result, PushResult(503))

        response.status_code = 429
        response.headers["Retry-After"] = "45"
        with patch("requests.Session.post", return_value=response) as post:
            result = asyncio.run(self.alerts.send(device, "inverter-offline", ttl=600, topic="inverter"))
        self.assertEqual(result, PushResult(429, retry_after=45))
        self.assertEqual(post.call_args.kwargs["headers"]["topic"], "inverter")

        response.status_code = 410
        with patch("requests.Session.post", return_value=response), patch("backend.services.push.TEST_INTERVAL", 0):
            self.assertEqual(client.post("/api/push/test", headers=auth).status_code, 410)
        self.assertEqual(client.get("/api/push/device", headers=auth).json(), {"endpoint": None})
        self.assertEqual(client.delete("/api/push/device", headers=auth).status_code, 204)


class PushEndpointTests(TestCase):
    def test_only_known_https_push_services(self):
        self.assertTrue(supported_endpoint("https://web.push.apple.com/subscription"))
        self.assertTrue(supported_endpoint("https://fcm.googleapis.com/fcm/send/id"))
        for endpoint in (
            "https://web.push.apple.com.evil.example/push",
            "https://web.push.apple.com@127.0.0.1/push",
            "http://web.push.apple.com/push",
            "https://web.push.apple.com:443/push",
            "https://fcm.googleapis.com/other",
            "https://web.push.apple.com\\@127.0.0.1/push",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertFalse(supported_endpoint(endpoint))
