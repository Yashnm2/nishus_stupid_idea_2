from __future__ import annotations

from datetime import datetime

from .chatbot import parse_command
from .ics import write_ics
from .importers import parse_timetable
from .models import ChatResponse, Plan
from .planner import apply_command, generate_plan
from .storage import load_plan, save_plan


def save_plan_and_calendar(plan: Plan) -> Plan:
    """Save the JSON plan and regenerate the matching ICS file."""
    plan.last_updated = datetime.now()
    save_plan(plan)
    write_ics(plan)
    return plan


def create_plan_from_timetable(filename: str, data: bytes) -> Plan:
    classes = parse_timetable(filename, data)
    if not classes:
        raise ValueError("No timetable rows matched patterns like 'Monday 09:00-11:00 Engineering Mathematics'.")
    return save_plan_and_calendar(generate_plan(classes))


async def handle_chat_message(message: str) -> ChatResponse:
    plan = load_plan()
    command = await parse_command(message)
    plan, reply, warnings = apply_command(plan, command)
    save_plan_and_calendar(plan)
    return ChatResponse(plan=plan, reply=reply, command=command, warnings=warnings)
