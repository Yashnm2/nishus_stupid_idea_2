from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

from .models import CalendarStatus, Plan, StudySession
from .storage import load_token, save_token


PROVIDERS = {
    "google": {
        "auth": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/calendar.events",
        "client_id": "GOOGLE_CLIENT_ID",
        "client_secret": "GOOGLE_CLIENT_SECRET",
        "redirect_uri": "GOOGLE_REDIRECT_URI",
    },
    "outlook": {
        "auth": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scope": "offline_access Calendars.ReadWrite",
        "client_id": "MICROSOFT_CLIENT_ID",
        "client_secret": "MICROSOFT_CLIENT_SECRET",
        "redirect_uri": "MICROSOFT_REDIRECT_URI",
    },
}


def _backend_base_url() -> str:
    base_url = os.environ.get("BACKEND_BASE_URL") or os.environ.get("API_BASE_URL")
    if not base_url:
        return "http://localhost:8001"
    base_url = base_url.rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    return base_url


def _default_redirect_uri(provider: str) -> str:
    return f"{_backend_base_url()}/api/calendar/{provider}/callback"


def _google_time_zone() -> str:
    return os.environ.get("GOOGLE_CALENDAR_TIME_ZONE") or os.environ.get("APP_TIME_ZONE") or "Asia/Singapore"


def _config(provider: str) -> dict:
    spec = PROVIDERS[provider]
    return {
        "client_id": os.environ.get(spec["client_id"]),
        "client_secret": os.environ.get(spec["client_secret"]),
        "redirect_uri": os.environ.get(spec["redirect_uri"], _default_redirect_uri(provider)),
        "scope": spec["scope"],
        "auth": spec["auth"],
        "token": spec["token"],
    }


def status(provider: str) -> CalendarStatus:
    cfg = _config(provider)
    configured = bool(cfg["client_id"] and cfg["client_secret"])
    connected = load_token(provider) is not None
    if not configured:
        message = f"{provider.title()} OAuth is not configured. Add client ID and secret environment variables."
    elif not connected:
        message = f"{provider.title()} is configured but not connected."
    else:
        message = f"{provider.title()} is connected."
    return CalendarStatus(provider=provider, configured=configured, connected=connected, message=message)


def auth_url(provider: str) -> str:
    cfg = _config(provider)
    if not cfg["client_id"]:
        raise ValueError(f"{provider.title()} client ID is not configured.")
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": cfg["scope"],
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{cfg['auth']}?{urlencode(params)}"


async def exchange_code(provider: str, code: str) -> None:
    cfg = _config(provider)
    payload = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": cfg["redirect_uri"],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(cfg["token"], data=payload)
        response.raise_for_status()
    save_token(provider, response.json())


def _event_payload(session: StudySession) -> dict:
    time_zone = _google_time_zone()
    return {
        "summary": f"Study: {session.module}",
        "description": "Adaptive study session",
        "start": {"dateTime": session.start.isoformat(), "timeZone": time_zone},
        "end": {"dateTime": session.end.isoformat(), "timeZone": time_zone},
    }


def _graph_payload(session: StudySession) -> dict:
    return {
        "subject": f"Study: {session.module}",
        "body": {"contentType": "text", "content": "Adaptive study session"},
        "start": {"dateTime": session.start.replace(tzinfo=None).isoformat(), "timeZone": "Singapore Standard Time"},
        "end": {"dateTime": session.end.replace(tzinfo=None).isoformat(), "timeZone": "Singapore Standard Time"},
    }


async def sync_plan(provider: str, plan: Plan) -> tuple[Plan, str]:
    token = load_token(provider)
    if token is None:
        raise ValueError(f"{provider.title()} is not connected.")
    access_token = token.get("access_token")
    if not access_token:
        raise ValueError(f"{provider.title()} token file does not contain an access token.")

    async with httpx.AsyncClient(timeout=30) as client:
        for session in plan.study_sessions:
            existing_id = session.calendar_event_ids.get(provider)
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            if provider == "google":
                body = _event_payload(session)
                if existing_id:
                    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{existing_id}"
                    response = await client.patch(url, headers=headers, json=body)
                else:
                    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
                    response = await client.post(url, headers=headers, json=body)
            else:
                body = _graph_payload(session)
                if existing_id:
                    url = f"https://graph.microsoft.com/v1.0/me/events/{existing_id}"
                    response = await client.patch(url, headers=headers, json=body)
                else:
                    url = "https://graph.microsoft.com/v1.0/me/events"
                    response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json() if response.content else {}
            if not existing_id and data.get("id"):
                session.calendar_event_ids[provider] = data["id"]
    return plan, f"Synced {len(plan.study_sessions)} session(s) to {provider.title()}."
