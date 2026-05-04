from __future__ import annotations

from datetime import datetime, timezone

from .models import Plan, StudySession
from .storage import ics_path


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _event(session: StudySession) -> str:
    uid = f"{session.id}@adaptive-study-planner.local"
    return "\r\n".join(
        [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_stamp(datetime.now())}",
            f"DTSTART:{_stamp(session.start)}",
            f"DTEND:{_stamp(session.end)}",
            f"SUMMARY:{_escape('Study: ' + session.module)}",
            f"DESCRIPTION:{_escape('Adaptive study session for ' + session.module)}",
            "END:VEVENT",
        ]
    )


def render_ics(plan: Plan) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Adaptive Study Planner//MVP//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    lines.extend(_event(session) for session in plan.study_sessions)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def write_ics(plan: Plan) -> str:
    content = render_ics(plan)
    ics_path().write_text(content, encoding="utf-8")
    return content

