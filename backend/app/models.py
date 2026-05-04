from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class ClassSession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("class"))
    day: str
    start: datetime
    end: datetime
    module: str
    source: str


class StudySession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("study"))
    module: str
    start: datetime
    end: datetime
    duration_minutes: int
    status: Literal["planned", "completed", "moved", "added", "resized"] = "planned"
    linked_class_id: str | None = None
    calendar_event_ids: dict[str, str] = Field(default_factory=dict)


class Preferences(BaseModel):
    quiet_hours_start: str = "22:00"
    earliest_study_time: str = "08:00"
    default_duration_minutes: int = 90
    study_delay_minutes: int = 60


class Plan(BaseModel):
    classes: list[ClassSession] = Field(default_factory=list)
    study_sessions: list[StudySession] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    module_priorities: dict[str, int] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)


class CommandType(str, Enum):
    move_session = "move_session"
    add_session = "add_session"
    resize_sessions = "resize_sessions"
    delete_session = "delete_session"
    mark_behind = "mark_behind"
    explain_schedule = "explain_schedule"


class ChatCommand(BaseModel):
    type: CommandType
    module: str | None = None
    to_day: str | None = None
    when: str | None = None
    duration_minutes: int | None = None
    date: str | None = None
    reason: str | None = None


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    plan: Plan
    reply: str
    command: ChatCommand | None = None
    warnings: list[str] = Field(default_factory=list)


class CalendarStatus(BaseModel):
    provider: Literal["google", "outlook"]
    configured: bool
    connected: bool
    message: str

