import asyncio

from app.models import CommandType
from app.services import create_plan_from_timetable, handle_chat_message


def test_create_plan_from_timetable_imports_classes_and_study_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDY_PLANNER_DATA_DIR", str(tmp_path))
    data = b"Monday 09:00-11:00 Engineering Mathematics"

    plan = create_plan_from_timetable("timetable.csv", data)

    assert len(plan.classes) == 1
    assert len(plan.study_sessions) == 1
    assert plan.classes[0].module == "Engineering Mathematics"


def test_handle_chat_message_returns_reply_and_updates_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDY_PLANNER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    create_plan_from_timetable("timetable.csv", b"Monday 09:00-11:00 Engineering Mathematics")

    response = asyncio.run(handle_chat_message("Move math to Friday"))

    assert response.command.type == CommandType.move_session
    assert "Moved" in response.reply
    assert response.plan.messages[-1] == response.reply
