from __future__ import annotations

from datetime import datetime, time, timedelta

from .models import ChatCommand, ClassSession, CommandType, Plan, StudySession


SLOT_MINUTES = 15
SEARCH_DAYS = 7
WEEK_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _parse_preference_time(value: str) -> time:
    hour, minute = [int(part) for part in value.split(":")]
    return time(hour, minute)


def _quiet_start(plan: Plan) -> time:
    return _parse_preference_time(plan.preferences.quiet_hours_start)


def _earliest(plan: Plan) -> time:
    return _parse_preference_time(plan.preferences.earliest_study_time)


def _overlaps(start: datetime, end: datetime, plan: Plan, ignore_id: str | None = None) -> bool:
    class_conflict = any(start < item.end and end > item.start for item in plan.classes)
    study_conflict = any(
        session.id != ignore_id and start < session.end and end > session.start
        for session in plan.study_sessions
    )
    return class_conflict or study_conflict


def _valid_window(start: datetime, end: datetime, plan: Plan) -> bool:
    if end.date() != start.date():
        return False
    earliest = datetime.combine(start.date(), _earliest(plan))
    quiet_start = datetime.combine(start.date(), _quiet_start(plan))
    return start >= earliest and end <= quiet_start


def _round_up_to_study_slot(start: datetime) -> datetime:
    candidate = start.replace(second=0, microsecond=0)
    if candidate.minute % SLOT_MINUTES:
        candidate += timedelta(minutes=SLOT_MINUTES - candidate.minute % SLOT_MINUTES)
    return candidate


def _next_morning(candidate: datetime, plan: Plan) -> datetime:
    return datetime.combine(candidate.date() + timedelta(days=1), _earliest(plan))


def nearest_valid_slot(
    start: datetime,
    duration_minutes: int,
    plan: Plan,
    ignore_id: str | None = None,
) -> tuple[datetime, datetime, str | None]:
    candidate = _round_up_to_study_slot(start)
    reason = None

    # Search a week ahead in small blocks. This keeps the algorithm simple enough
    # for the assignment while still avoiding obvious clashes and quiet hours.
    for _ in range(SEARCH_DAYS * 24 * (60 // SLOT_MINUTES)):
        end = candidate + timedelta(minutes=duration_minutes)
        if _valid_window(candidate, end, plan) and not _overlaps(candidate, end, plan, ignore_id):
            if candidate != start.replace(second=0, microsecond=0):
                reason = "The requested time conflicted with another class/session or quiet hours, so I used the nearest valid slot."
            return candidate, end, reason
        candidate += timedelta(minutes=SLOT_MINUTES)
        if candidate.time() >= _quiet_start(plan):
            candidate = _next_morning(candidate, plan)
    raise ValueError("No valid study slot found in the next week.")


def _preferred_session_start(class_session: ClassSession, plan: Plan) -> datetime:
    desired = class_session.end + timedelta(minutes=plan.preferences.study_delay_minutes)
    desired_end = desired + timedelta(minutes=plan.preferences.default_duration_minutes)
    if _valid_window(desired, desired_end, plan):
        return desired
    return datetime.combine(class_session.start.date() + timedelta(days=1), _earliest(plan))


def generate_plan(classes: list[ClassSession]) -> Plan:
    plan = Plan(classes=classes)
    for class_session in sorted(classes, key=lambda cls: cls.start):
        desired = _preferred_session_start(class_session, plan)
        start, end, _ = nearest_valid_slot(desired, plan.preferences.default_duration_minutes, plan)
        plan.study_sessions.append(
            StudySession(
                module=class_session.module,
                start=start,
                end=end,
                duration_minutes=plan.preferences.default_duration_minutes,
                linked_class_id=class_session.id,
            )
        )
    plan.last_updated = datetime.now()
    return plan


def _module_matches(plan: Plan, module: str | None) -> list[StudySession]:
    if not module:
        return []
    lowered = module.lower()
    return [session for session in plan.study_sessions if lowered in session.module.lower()]


def _day_to_date(plan: Plan, day: str) -> datetime:
    first = min([s.start for s in plan.study_sessions] + [c.start for c in plan.classes], default=datetime.now())
    monday = first.date() - timedelta(days=first.weekday())
    return datetime.combine(monday + timedelta(days=WEEK_DAYS.index(day.lower())), _earliest(plan))


def _append_warning(warnings: list[str], reason: str | None) -> None:
    if reason:
        warnings.append(reason)


def _add_study_session(
    plan: Plan,
    module: str,
    desired: datetime,
    duration_minutes: int,
    warnings: list[str],
) -> StudySession:
    start, end, reason = nearest_valid_slot(desired, duration_minutes, plan)
    session = StudySession(module=module, start=start, end=end, duration_minutes=duration_minutes, status="added")
    plan.study_sessions.append(session)
    _append_warning(warnings, reason)
    return session


def _explain_schedule(plan: Plan) -> str:
    modules = ", ".join(sorted({session.module for session in plan.study_sessions})) or "no modules yet"
    return f"Your plan has {len(plan.study_sessions)} study sessions covering {modules}."


def _handle_mark_behind(plan: Plan, command: ChatCommand, warnings: list[str]) -> str:
    if not command.module:
        raise ValueError("Tell me which module is behind.")
    plan.module_priorities[command.module] = plan.module_priorities.get(command.module, 0) + 1
    duration = command.duration_minutes or 60
    desired = datetime.now() + timedelta(days=1)
    desired = datetime.combine(desired.date(), _earliest(plan))
    _add_study_session(plan, command.module, desired, duration, warnings)
    return f"Added an extra {duration}-minute {command.module} session."


def _handle_add_session(plan: Plan, command: ChatCommand, warnings: list[str]) -> str:
    if not command.module:
        raise ValueError("Tell me which module to add.")
    duration = command.duration_minutes or 60
    desired = datetime.now()
    if command.when and "tomorrow" in command.when.lower():
        desired += timedelta(days=1)
    desired = datetime.combine(desired.date(), _earliest(plan))
    _add_study_session(plan, command.module, desired, duration, warnings)
    return f"Added a {duration}-minute {command.module} session."


def _handle_move_session(plan: Plan, command: ChatCommand, warnings: list[str]) -> str:
    matches = _module_matches(plan, command.module)
    if not matches:
        raise ValueError(f"No study session matched module '{command.module}'.")
    if not command.to_day:
        raise ValueError("Tell me which day to move the session to.")

    session = sorted(matches, key=lambda item: item.start)[0]
    start, end, reason = nearest_valid_slot(
        _day_to_date(plan, command.to_day),
        session.duration_minutes,
        plan,
        ignore_id=session.id,
    )
    session.start = start
    session.end = end
    session.status = "moved"
    _append_warning(warnings, reason)
    return f"Moved {session.module} to {start.strftime('%A %H:%M')}."


def _handle_resize_sessions(plan: Plan, command: ChatCommand, warnings: list[str]) -> str:
    duration = command.duration_minutes
    if not duration:
        raise ValueError("Tell me the new duration.")
    matches = _module_matches(plan, command.module) if command.module else plan.study_sessions
    if not matches:
        raise ValueError("No sessions matched that resize request.")

    for session in matches:
        start, end, reason = nearest_valid_slot(session.start, duration, plan, ignore_id=session.id)
        session.start = start
        session.end = end
        session.duration_minutes = duration
        session.status = "resized"
        _append_warning(warnings, reason)
    return f"Resized {len(matches)} session(s) to {duration} minutes."


def _handle_delete_session(plan: Plan, command: ChatCommand) -> str:
    matches = _module_matches(plan, command.module)
    before = len(plan.study_sessions)
    plan.study_sessions = [session for session in plan.study_sessions if session not in matches]
    return f"Deleted {before - len(plan.study_sessions)} session(s)."


def apply_command(plan: Plan, command: ChatCommand) -> tuple[Plan, str, list[str]]:
    warnings: list[str] = []
    if command.type == CommandType.explain_schedule:
        return plan, _explain_schedule(plan), warnings

    if command.type == CommandType.mark_behind:
        reply = _handle_mark_behind(plan, command, warnings)
    elif command.type == CommandType.add_session:
        reply = _handle_add_session(plan, command, warnings)
    elif command.type == CommandType.move_session:
        reply = _handle_move_session(plan, command, warnings)
    elif command.type == CommandType.resize_sessions:
        reply = _handle_resize_sessions(plan, command, warnings)
    elif command.type == CommandType.delete_session:
        reply = _handle_delete_session(plan, command)
    else:
        reply = "Plan updated."

    plan.last_updated = datetime.now()
    plan.messages.append(reply)
    return plan, reply, sorted(set(warnings))
