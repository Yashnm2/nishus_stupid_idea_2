from __future__ import annotations

from datetime import datetime, time, timedelta

from .models import ChatCommand, ClassSession, CommandType, Plan, StudySession


def _quiet_start(plan: Plan) -> time:
    hour, minute = [int(part) for part in plan.preferences.quiet_hours_start.split(":")]
    return time(hour, minute)


def _earliest(plan: Plan) -> time:
    hour, minute = [int(part) for part in plan.preferences.earliest_study_time.split(":")]
    return time(hour, minute)


def _overlaps(start: datetime, end: datetime, plan: Plan, ignore_id: str | None = None) -> bool:
    class_conflict = any(start < item.end and end > item.start for item in plan.classes)
    study_conflict = any(
        session.id != ignore_id and start < session.end and end > session.start
        for session in plan.study_sessions
    )
    return class_conflict or study_conflict


def _valid_window(start: datetime, end: datetime, plan: Plan) -> bool:
    return start.time() >= _earliest(plan) and end.time() <= _quiet_start(plan)


def nearest_valid_slot(
    start: datetime,
    duration_minutes: int,
    plan: Plan,
    ignore_id: str | None = None,
) -> tuple[datetime, datetime, str | None]:
    candidate = start.replace(second=0, microsecond=0)
    if candidate.minute % 15:
        candidate += timedelta(minutes=15 - candidate.minute % 15)
    reason = None
    for _ in range(7 * 24 * 4):
        end = candidate + timedelta(minutes=duration_minutes)
        if _valid_window(candidate, end, plan) and not _overlaps(candidate, end, plan, ignore_id):
            if candidate != start.replace(second=0, microsecond=0):
                reason = "The requested time conflicted with another class/session or quiet hours, so I used the nearest valid slot."
            return candidate, end, reason
        candidate += timedelta(minutes=15)
        if candidate.time() >= _quiet_start(plan):
            candidate = datetime.combine(candidate.date() + timedelta(days=1), _earliest(plan))
    raise ValueError("No valid study slot found in the next week.")


def generate_plan(classes: list[ClassSession]) -> Plan:
    plan = Plan(classes=classes)
    for item in sorted(classes, key=lambda cls: cls.start):
        desired = item.end + timedelta(minutes=plan.preferences.study_delay_minutes)
        if (desired + timedelta(minutes=plan.preferences.default_duration_minutes)).time() > _quiet_start(plan):
            desired = datetime.combine(item.start.date() + timedelta(days=1), _earliest(plan))
        start, end, _ = nearest_valid_slot(desired, plan.preferences.default_duration_minutes, plan)
        plan.study_sessions.append(
            StudySession(
                module=item.module,
                start=start,
                end=end,
                duration_minutes=plan.preferences.default_duration_minutes,
                linked_class_id=item.id,
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
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return datetime.combine(monday + timedelta(days=days.index(day.lower())), _earliest(plan))


def apply_command(plan: Plan, command: ChatCommand) -> tuple[Plan, str, list[str]]:
    warnings: list[str] = []
    reply = "Plan updated."
    if command.type == CommandType.explain_schedule:
        modules = ", ".join(sorted({s.module for s in plan.study_sessions})) or "no modules yet"
        return plan, f"Your plan has {len(plan.study_sessions)} study sessions covering {modules}.", warnings

    if command.type == CommandType.mark_behind:
        if not command.module:
            raise ValueError("Tell me which module is behind.")
        plan.module_priorities[command.module] = plan.module_priorities.get(command.module, 0) + 1
        duration = command.duration_minutes or 60
        desired = datetime.now() + timedelta(days=1)
        desired = datetime.combine(desired.date(), _earliest(plan))
        start, end, reason = nearest_valid_slot(desired, duration, plan)
        plan.study_sessions.append(
            StudySession(module=command.module, start=start, end=end, duration_minutes=duration, status="added")
        )
        if reason:
            warnings.append(reason)
        reply = f"Added an extra {duration}-minute {command.module} session."

    elif command.type == CommandType.add_session:
        if not command.module:
            raise ValueError("Tell me which module to add.")
        duration = command.duration_minutes or 60
        desired = datetime.now()
        if command.when and "tomorrow" in command.when.lower():
            desired += timedelta(days=1)
        desired = datetime.combine(desired.date(), _earliest(plan))
        start, end, reason = nearest_valid_slot(desired, duration, plan)
        plan.study_sessions.append(
            StudySession(module=command.module, start=start, end=end, duration_minutes=duration, status="added")
        )
        if reason:
            warnings.append(reason)
        reply = f"Added a {duration}-minute {command.module} session."

    elif command.type == CommandType.move_session:
        matches = _module_matches(plan, command.module)
        if not matches:
            raise ValueError(f"No study session matched module '{command.module}'.")
        if not command.to_day:
            raise ValueError("Tell me which day to move the session to.")
        target_base = _day_to_date(plan, command.to_day)
        session = sorted(matches, key=lambda s: s.start)[0]
        start, end, reason = nearest_valid_slot(target_base, session.duration_minutes, plan, ignore_id=session.id)
        session.start = start
        session.end = end
        session.status = "moved"
        if reason:
            warnings.append(reason)
        reply = f"Moved {session.module} to {start.strftime('%A %H:%M')}."

    elif command.type == CommandType.resize_sessions:
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
            if reason:
                warnings.append(reason)
        reply = f"Resized {len(matches)} session(s) to {duration} minutes."

    elif command.type == CommandType.delete_session:
        matches = _module_matches(plan, command.module)
        before = len(plan.study_sessions)
        plan.study_sessions = [session for session in plan.study_sessions if session not in matches]
        reply = f"Deleted {before - len(plan.study_sessions)} session(s)."

    plan.last_updated = datetime.now()
    plan.messages.append(reply)
    return plan, reply, sorted(set(warnings))

