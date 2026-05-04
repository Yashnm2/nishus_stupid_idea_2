import asyncio

from app.chatbot import parse_command
from app.models import CommandType


def test_fallback_parser_handles_move_command(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    command = asyncio.run(parse_command("Move math to Friday"))

    assert command.type == CommandType.move_session
    assert command.module == "Math"
    assert command.to_day == "Friday"


def test_fallback_parser_handles_resize_command(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    command = asyncio.run(parse_command("I can only study 30 minutes today"))

    assert command.type == CommandType.resize_sessions
    assert command.duration_minutes == 30
