from __future__ import annotations

from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from . import calendar_sync
from .chatbot import parse_command
from .ics import write_ics
from .importers import parse_timetable
from .models import ChatRequest, ChatResponse
from .planner import apply_command, generate_plan
from .storage import ics_path, load_plan, save_plan


load_dotenv()

app = FastAPI(title="Adaptive Student Study Planner")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def persist(plan):
    plan.last_updated = datetime.now()
    save_plan(plan)
    write_ics(plan)
    return plan


@app.get("/api/plan")
def get_plan():
    return load_plan()


@app.post("/api/upload")
async def upload_timetable(file: UploadFile = File(...)):
    try:
        classes = parse_timetable(file.filename or "upload", await file.read())
        if not classes:
            raise ValueError("No timetable rows matched patterns like 'Monday 09:00-11:00 Engineering Mathematics'.")
        plan = generate_plan(classes)
        return persist(plan)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    plan = load_plan()
    try:
        command = await parse_command(request.message)
        plan, reply, warnings = apply_command(plan, command)
        persist(plan)
        return ChatResponse(plan=plan, reply=reply, command=command, warnings=warnings)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/export/ics")
def export_ics():
    plan = load_plan()
    write_ics(plan)
    return FileResponse(ics_path(), media_type="text/calendar", filename="study_plan.ics")


@app.get("/api/calendar/status")
def calendar_status():
    return [calendar_sync.status("google"), calendar_sync.status("outlook")]


@app.get("/api/calendar/{provider}/auth-url")
def calendar_auth_url(provider: str):
    if provider not in calendar_sync.PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown calendar provider.")
    try:
        return {"url": calendar_sync.auth_url(provider)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/calendar/{provider}/callback")
async def calendar_callback(provider: str, code: str):
    if provider not in calendar_sync.PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown calendar provider.")
    try:
        await calendar_sync.exchange_code(provider, code)
        return HTMLResponse("<p>Calendar connected. You can return to the study planner.</p>")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calendar/{provider}/sync")
async def sync_calendar(provider: str):
    if provider not in calendar_sync.PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown calendar provider.")
    try:
        plan, message = await calendar_sync.sync_plan(provider, load_plan())
        persist(plan)
        return {"message": message, "plan": plan}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
