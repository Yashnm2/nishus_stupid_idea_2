from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Plan


def app_data_dir() -> Path:
    base = os.environ.get("STUDY_PLANNER_DATA_DIR")
    if base:
        root = Path(base)
    else:
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
        root = root / "AdaptiveStudyPlanner"
    root.mkdir(parents=True, exist_ok=True)
    (root / "tokens").mkdir(parents=True, exist_ok=True)
    return root


def plan_path() -> Path:
    return app_data_dir() / "plan.json"


def ics_path() -> Path:
    return app_data_dir() / "study_plan.ics"


def token_path(provider: str) -> Path:
    return app_data_dir() / "tokens" / f"{provider}.json"


def load_plan() -> Plan:
    path = plan_path()
    if not path.exists():
        return Plan()
    return Plan.model_validate_json(path.read_text(encoding="utf-8"))


def save_plan(plan: Plan) -> Plan:
    path = plan_path()
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return plan


def load_token(provider: str) -> dict | None:
    path = token_path(provider)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_token(provider: str, token: dict) -> None:
    path = token_path(provider)
    path.write_text(json.dumps(token, indent=2), encoding="utf-8")

