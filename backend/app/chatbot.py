from __future__ import annotations

import json
import os
import re

import httpx

from .models import ChatCommand, CommandType


SYSTEM_PROMPT = """
You convert student study-planner messages into strict JSON.
Allowed types: move_session, add_session, resize_sessions, delete_session, mark_behind, explain_schedule.
Fields: type, module, to_day, when, duration_minutes, date, reason.
Return JSON only. Use null for unknown optional fields.
"""


def _fallback_parse(message: str) -> ChatCommand:
    text = message.lower()
    duration_match = re.search(r"(\d+)\s*(?:min|minute)", text)
    duration = int(duration_match.group(1)) if duration_match else None
    day_match = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
    module_match = re.search(r"(?:math|physics|chemistry|biology|english|history|engineering mathematics|economics|computing)", text)
    module = module_match.group(0).title() if module_match else None

    if "explain" in text or "why" in text:
        return ChatCommand(type=CommandType.explain_schedule)
    if "behind" in text:
        return ChatCommand(type=CommandType.mark_behind, module=module, duration_minutes=duration)
    if "move" in text:
        return ChatCommand(type=CommandType.move_session, module=module, to_day=day_match.group(1).title() if day_match else None)
    if "delete" in text or "remove" in text or "cancel" in text:
        return ChatCommand(type=CommandType.delete_session, module=module)
    if duration and ("only" in text or "resize" in text or "shorter" in text):
        return ChatCommand(type=CommandType.resize_sessions, module=module, duration_minutes=duration)
    return ChatCommand(type=CommandType.add_session, module=module, duration_minutes=duration, when="tomorrow" if "tomorrow" in text else None)


async def parse_command(message: str) -> ChatCommand:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _fallback_parse(message)

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    try:
        return ChatCommand.model_validate(json.loads(content))
    except Exception as exc:
        raise ValueError(f"LLM returned an invalid command: {content}") from exc

