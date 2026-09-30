import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from backend.api import assistant as assistant_api
from backend.app import create_app
from backend.runtime import AppRuntime
from providers.base import Metrics, Provider, VN_TZ
from providers.evn import EvnTariff
from providers.history import HistoryStore


class FakeProvider(Provider):
    name = "mock"
    battery_reserve_percent = 20.0

    async def get_metrics(self) -> Metrics:
        return Metrics(source="mock", status="online", battery_soc=80)


class FakeAssistant:
    chat_enabled = True

    def __init__(self) -> None:
        self.seen: dict = {}

    async def chat_stream(self, context, messages, lang="en", tools=None):
        self.seen = {"context": context, "messages": messages, "lang": lang}
        yield {"type": "status", "tool": "get_day_detail"}
        await tools["propose_action"]["fn"]({"action": "set_reserve", "reserve_pct": 40, "reason": "rain"})
        yield {"type": "delta", "text": "Keep more "}
        yield {"type": "delta", "text": "battery tonight."}


def _events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


class AssistantApiTests(TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.tmp.name) / "history.db")
        self.provider = FakeProvider()
        self.assistant = FakeAssistant()
        self.runtime = AppRuntime(
            root=Path(self.tmp.name),
            config={"source": "mock", "currency": "VND", "battery_reserve_percent": 20},
            live_provider=self.provider,
            history_provider=self.provider,
            poll_interval=5,
            store=self.store,
            tariff=EvnTariff(),
            assistant=self.assistant,  # type: ignore[arg-type]
        )
        assistant_api._last_turn["at"] = None
        self.client_context = TestClient(create_app(self.runtime, mount_static=False))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.tmp.cleanup()

    def test_chat_streams_status_text_and_actions(self) -> None:
        response = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "Rain tomorrow?"}]})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        events = _events(response.text)
        self.assertEqual([e["type"] for e in events], ["status", "delta", "delta", "done"])
        self.assertEqual(events[-1]["actions"][0]["params"], {"reserve_pct": 40})
        self.assertEqual(self.assistant.seen["lang"], "en")
        self.assertIn("this_bill_cycle", self.assistant.seen["context"])

    def test_chat_too_fast_is_rate_limited(self) -> None:
        self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        again = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

        self.assertEqual(again.status_code, 429)
        self.assertEqual(again.json()["error_code"], "rate_limit")

    def test_disabled_assistant(self) -> None:
        self.runtime.assistant = None

        self.assertEqual(self.client.get("/api/ai_status").json(), {"enabled": False})
        self.assertEqual(self.client.post("/api/chat", json={}).json(), {"enabled": False})

    def test_action_applies_bounded_reserve(self) -> None:
        bad = self.client.post("/api/action", json={"kind": "set_reserve", "params": {"reserve_pct": 95}})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["error_code"], "out_of_range")

        ok = self.client.post("/api/action", json={"kind": "set_reserve", "params": {"reserve_pct": 35}})
        self.assertEqual(ok.json(), {"ok": True, "kind": "set_reserve", "old": 20.0, "new": 35})
        self.assertEqual(self.runtime.config["battery_reserve_percent"], 35)
        self.assertEqual(self.provider.battery_reserve_percent, 35.0)
        self.assertFalse((Path(self.tmp.name) / "config.json").exists())

    def test_status_sync_and_export(self) -> None:
        self.store.backfill_energy({"2026-09-01": {"cons": 40.0, "buy": 8.0}})

        status = self.client.get("/api/status").json()
        self.assertEqual(status["history"], {"days": 1, "first_day": "2026-09-01", "last_day": "2026-09-01"})
        self.assertFalse(status["sync"]["supported"])
        self.assertTrue(status["assistant"])
        self.assertEqual(status["battery_reserve_percent"], 20)

        self.runtime.last_sync = {"finished_at": datetime.now(VN_TZ).isoformat(timespec="seconds")}
        too_soon = self.client.post("/api/sync")
        self.assertEqual(too_soon.status_code, 429)
        self.assertEqual(too_soon.json()["reason"], "too_soon")

        self.runtime.last_sync = None
        self.assertEqual(self.client.post("/api/sync").json(), {"ok": True})

        csv_response = self.client.get("/api/export.csv")
        self.assertIn("attachment", csv_response.headers["content-disposition"])
        self.assertEqual(csv_response.text.splitlines(), [
            "day,generation_kwh,consumption_kwh,grid_buy_kwh",
            "2026-09-01,,40.0,8.0",
        ])

    def test_notices_list_and_dismiss(self) -> None:
        expires = (datetime.now(VN_TZ) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        self.store.notice_add("night_load_high", "2026-09-29", "warn", {"night_kwh": 40.3, "avg_kwh": 23.9}, expires)

        notices = self.client.get("/api/notices").json()["notices"]
        self.assertEqual(notices[0]["data"]["night_kwh"], 40.3)

        self.assertEqual(self.client.post(f"/api/notices/{notices[0]['id']}/dismiss").json(), {"ok": True})
        self.assertEqual(self.client.get("/api/notices").json()["notices"], [])
