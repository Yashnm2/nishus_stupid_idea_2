import asyncio
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from app.calendar_sync import _event_payload, auth_url, sync_plan
from app.importers import parse_entry
from app.models import StudySession
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


def test_google_auth_url_defaults_to_documented_backend_port(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("API_BASE_URL", raising=False)

    params = parse_qs(urlparse(auth_url("google")).query)

    assert params["redirect_uri"] == ["http://localhost:8001/api/calendar/google/callback"]


def test_google_auth_url_uses_configured_backend_base_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("BACKEND_BASE_URL", "http://localhost:9000")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)

    params = parse_qs(urlparse(auth_url("google")).query)

    assert params["redirect_uri"] == ["http://localhost:9000/api/calendar/google/callback"]


def test_google_event_payload_uses_iana_time_zone(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_TIME_ZONE", "Asia/Singapore")
    start = datetime(2026, 5, 4, 9, 0)
    session = StudySession(
        module="Engineering Mathematics",
        start=start,
        end=start + timedelta(minutes=90),
        duration_minutes=90,
    )

    payload = _event_payload(session)

    assert payload["start"]["timeZone"] == "Asia/Singapore"
    assert payload["end"]["timeZone"] == "Asia/Singapore"
