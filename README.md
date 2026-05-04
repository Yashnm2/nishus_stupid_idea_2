# Adaptive Student Study Planner

Local MVP for importing a school timetable, generating study blocks, editing the plan through a chatbot, exporting an `.ics` calendar, and syncing to Google Calendar or Outlook when OAuth credentials are configured.

## Run locally

Backend:

```powershell
cd C:\Users\USER\Downloads\nishus_stupid_idea
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8001
```

Frontend:

```powershell
cd C:\Users\USER\Downloads\nishus_stupid_idea\frontend
npm install
npm run dev -- --port 5174 --host 127.0.0.1
```

Open `http://127.0.0.1:5174`.

If another app is already using a port, choose a free frontend port and keep `frontend/.env` pointed at the backend:

```text
VITE_API_BASE_URL=http://localhost:8001/api
```

## Optional configuration

Create `backend/.env` or set environment variables:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8001/api/calendar/google/callback
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_REDIRECT_URI=http://localhost:8001/api/calendar/outlook/callback
```

Without `OPENAI_API_KEY`, the chatbot uses a deterministic fallback parser for the initial command set. Without calendar credentials, `.ics` export still works and sync endpoints report configuration guidance.

Local app state is stored outside the repo by default at:

```text
%LOCALAPPDATA%\AdaptiveStudyPlanner
```
