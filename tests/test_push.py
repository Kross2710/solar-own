from base64 import urlsafe_b64encode
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.runtime import create_runtime
from backend.services.push import OUTAGE_SECONDS, PushAlerts, supported_endpoint


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

    def test_enrollment_test_delivery_and_retirement(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from requests import Response

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
