import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.api import assistant as assistant_api
from backend.app import create_app
from backend.config import load_config
from backend.runtime import AppRuntime
from providers.assistant import Assistant
from providers.base import Metrics, Provider, VN_TZ
from providers.evn import EvnTariff
from providers.history import HistoryStore


class FakeProvider(Provider):
    name = "mock"

    async def get_metrics(self) -> Metrics:
        return Metrics(source="mock", status="online", battery_soc=80)


class FakeAssistant:
    chat_enabled = True

    def __init__(self) -> None:
        self.seen: dict = {}

    async def chat_stream(self, context, messages, lang="en", tools=None):
        self.seen = {"context": context, "messages": messages, "lang": lang}
        self.seen["tools"] = set(tools)
        yield {"type": "status", "tool": "get_day_detail"}
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

    def test_chat_streams_status_text_and_done(self) -> None:
        response = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "Rain tomorrow?"}]})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        events = _events(response.text)
        self.assertEqual([e["type"] for e in events], ["status", "delta", "delta", "done"])
        self.assertEqual(events[-1]["actions"], [])
        self.assertNotIn("propose_action", self.assistant.seen["tools"])
        self.assertIn("get_day_detail", self.assistant.seen["tools"])
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

    def test_openai_compatible_chat_streams_reply(self) -> None:
        requests = []

        def complete(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "<think>Draft</think> Save power tonight."}}],
            })

        upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(complete))
        self.runtime.assistant = Assistant({
            "provider": "openrouter",
            "model": "example/solar-model",
            "api_key": "test-openrouter-key",
        })

        self.assertEqual(self.client.get("/api/ai_status").json(), {"enabled": True})
        with patch("providers.assistant.httpx.AsyncClient", return_value=upstream_client):
            response = self.client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Rain tomorrow?"}],
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(_events(response.text), [
            {"type": "delta", "text": "Save power tonight."},
            {"type": "done", "actions": []},
        ])
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(str(request.url), "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer test-openrouter-key")
        body = json.loads(request.content)
        self.assertEqual(body["model"], "example/solar-model")
        self.assertEqual(body["messages"][-1], {"role": "user", "content": "Rain tomorrow?"})
        self.assertIn("this_bill_cycle", body["messages"][0]["content"])
        self.assertNotIn("You have TOOLS", body["messages"][0]["content"])
        self.assertNotIn("tools", body)

    def test_openai_compatible_credentials_are_provider_specific(self) -> None:
        config_path = Path(self.tmp.name) / "config.json"
        config_path.write_text(json.dumps({
            "ai": {"provider": "openai", "model": "model", "base_url": "http://localhost:1234/v1", "api_key": "file-key"},
        }), encoding="utf-8")
        with patch.dict(os.environ, {"SOLAR_GEMINI_API_KEY": "gemini-key"}, clear=True):
            self.assertEqual(load_config(config_path.parent)["ai"]["api_key"], "file-key")
        with patch.dict(os.environ, {"SOLAR_OPENAI_API_KEY": "openai-key"}, clear=True):
            config = load_config(config_path.parent)["ai"]
            self.assertEqual(config["api_key"], "openai-key")
            self.assertTrue(Assistant(config).chat_enabled)

    def test_status_sync_and_export(self) -> None:
        self.store.backfill_energy({"2026-09-01": {"cons": 40.0, "buy": 8.0}})

        status = self.client.get("/api/status").json()
        self.assertEqual(status["history"], {"days": 1, "first_day": "2026-09-01", "last_day": "2026-09-01"})
        self.assertFalse(status["sync"]["supported"])
        self.assertTrue(status["assistant"])
        self.assertNotIn("battery_reserve_percent", status)
        self.assertEqual(self.client.post("/api/action", json={"kind": "set_reserve"}).status_code, 404)

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
