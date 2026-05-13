from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from . import calendar_sync
from .ics import write_ics
from .models import ChatRequest, ChatResponse
from .services import create_plan_from_timetable, handle_chat_message, save_plan_and_calendar
from .storage import ics_path, load_plan


load_dotenv()

app = FastAPI(title="Adaptive Student Study Planner")

# The frontend is usually served by Vite on a local port during demos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_calendar_provider(provider: str) -> None:
    try:
        calendar_sync.ensure_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# Plan and timetable endpoints
@app.get("/api/plan")
def get_plan():
    return load_plan()


@app.post("/api/upload")
async def upload_timetable(file: UploadFile = File(...)):
    try:
        return create_plan_from_timetable(file.filename or "upload", await file.read())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        return await handle_chat_message(request.message)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/export/ics")
def export_ics():
    plan = load_plan()
    write_ics(plan)
    return FileResponse(ics_path(), media_type="text/calendar", filename="study_plan.ics")


# Optional calendar sync endpoints
@app.get("/api/calendar/status")
def calendar_status():
    return [calendar_sync.status("google"), calendar_sync.status("outlook")]


@app.get("/api/calendar/{provider}/auth-url")
def calendar_auth_url(provider: str):
    ensure_calendar_provider(provider)
    try:
        return {"url": calendar_sync.auth_url(provider)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/calendar/{provider}/callback")
async def calendar_callback(provider: str, code: str):
    ensure_calendar_provider(provider)
    try:
        await calendar_sync.exchange_code(provider, code)
        return HTMLResponse("<p>Calendar connected. You can return to the study planner.</p>")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calendar/{provider}/sync")
async def sync_calendar(provider: str):
    ensure_calendar_provider(provider)
    try:
        plan, message = await calendar_sync.sync_plan(provider, load_plan())
        save_plan_and_calendar(plan)
        return {"message": message, "plan": plan}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
