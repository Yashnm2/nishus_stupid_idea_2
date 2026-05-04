import asyncio

from app.calendar_sync import sync_plan
from app.importers import parse_entry
from app.planner import generate_plan


class FakeResponse:
    content = b"{}"

    def __init__(self, event_id):
        self._event_id = event_id

    def raise_for_status(self):
        return None

    def json(self):
        return {"id": self._event_id}


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return FakeResponse("evt_123")

    async def patch(self, url, **kwargs):
        self.calls.append(("patch", url, kwargs))
        return FakeResponse("evt_123")


def test_google_sync_reuses_event_ids(monkeypatch):
    plan = generate_plan([parse_entry("Monday 09:00-11:00 Engineering Mathematics", "test")])
    monkeypatch.setattr("app.calendar_sync.load_token", lambda provider: {"access_token": "token"})
    monkeypatch.setattr("app.calendar_sync.httpx.AsyncClient", FakeClient)

    plan, message = asyncio.run(sync_plan("google", plan))
    assert plan.study_sessions[0].calendar_event_ids["google"] == "evt_123"

    plan, message = asyncio.run(sync_plan("google", plan))
    assert "Synced" in message
