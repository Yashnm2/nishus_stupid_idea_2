from app.ics import render_ics
from app.importers import parse_entry
from app.planner import generate_plan


def test_render_ics_includes_stable_event_uids():
    plan = generate_plan([parse_entry("Monday 09:00-11:00 Engineering Mathematics", "test")])

    content = render_ics(plan)

    assert "BEGIN:VCALENDAR" in content
    assert "SUMMARY:Study: Engineering Mathematics" in content
    assert f"UID:{plan.study_sessions[0].id}@adaptive-study-planner.local" in content

