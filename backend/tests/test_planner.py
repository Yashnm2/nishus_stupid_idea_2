from app.importers import parse_entry
from app.models import ChatCommand, CommandType
from app.planner import apply_command, generate_plan


def make_plan():
    classes = [
        parse_entry("Monday 09:00-11:00 Engineering Mathematics", "test"),
        parse_entry("Tuesday 14:00-15:00 Physics Lab", "test"),
    ]
    return generate_plan(classes)


def test_generate_plan_creates_one_study_session_per_class():
    plan = make_plan()

    assert len(plan.study_sessions) == 2
    assert plan.study_sessions[0].duration_minutes == 90
    assert plan.study_sessions[0].start.hour >= 8
    assert plan.study_sessions[0].end.hour <= 22


def test_generate_plan_rejects_sessions_crossing_quiet_hours():
    plan = generate_plan([parse_entry("Monday 20:45-21:45 Late Seminar", "test")])

    session = plan.study_sessions[0]
    assert session.start.strftime("%A") == "Tuesday"
    assert session.start.hour == 8
    assert session.end.date() == session.start.date()
    assert session.end.hour < 22 or (session.end.hour == 22 and session.end.minute == 0)


def test_move_command_uses_requested_day():
    plan = make_plan()

    plan, reply, warnings = apply_command(
        plan,
        ChatCommand(type=CommandType.move_session, module="Engineering", to_day="Friday"),
    )

    moved = next(session for session in plan.study_sessions if "Engineering" in session.module)
    assert moved.start.strftime("%A") == "Friday"
    assert "Moved" in reply


def test_resize_command_changes_duration():
    plan = make_plan()

    plan, reply, warnings = apply_command(
        plan,
        ChatCommand(type=CommandType.resize_sessions, duration_minutes=30),
    )

    assert all(session.duration_minutes == 30 for session in plan.study_sessions)
    assert "Resized" in reply


def test_mark_behind_adds_extra_session_and_priority():
    plan = make_plan()

    plan, reply, warnings = apply_command(
        plan,
        ChatCommand(type=CommandType.mark_behind, module="Physics", duration_minutes=60),
    )

    assert plan.module_priorities["Physics"] == 1
    assert len([session for session in plan.study_sessions if "Physics" in session.module]) == 2
    assert "Added" in reply
