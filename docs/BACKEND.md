# Backend Guide

This backend is a small FastAPI app for the Adaptive Student Study Planner. It keeps the assignment logic local and readable: import a timetable, generate study sessions, edit the plan through chat commands, export an ICS file, and optionally sync sessions to Google Calendar or Outlook.

## Main Flow

1. `POST /api/upload` receives a timetable file.
2. `app.importers` extracts class sessions from CSV, XLSX, ODS, or PDF rows.
3. `app.planner.generate_plan` creates one study session after each class, while avoiding class clashes, study clashes, and quiet hours.
4. `app.services.save_plan_and_calendar` stores the plan as JSON and regenerates the ICS calendar file.
5. `POST /api/chat` turns a student message into a `ChatCommand`, applies it to the saved plan, and saves the updated result.

## Important Files

- `app/main.py`: FastAPI routes. This file should stay thin and mostly call service functions.
- `app/services.py`: Application-level actions used by the routes, such as importing a timetable or handling a chat message.
- `app/models.py`: Pydantic models for classes, study sessions, preferences, plans, chat requests, and calendar status.
- `app/importers.py`: File parsing logic. It normalizes timetable text into `ClassSession` objects.
- `app/planner.py`: Scheduling rules and chat command handling. This is where the main assignment logic lives.
- `app/chatbot.py`: Converts chat text into structured commands. It uses OpenAI when configured, otherwise it uses a deterministic fallback parser for demos/tests.
- `app/ics.py`: Renders study sessions as an `.ics` calendar file.
- `app/calendar_sync.py`: Optional Google/Outlook OAuth and event sync logic.
- `app/storage.py`: Local JSON/token file storage.

## Scheduling Rules

The planner intentionally uses simple rules:

- Study sessions are placed after class sessions by default.
- Sessions cannot overlap existing classes or study sessions.
- Sessions must stay within the same day.
- The default study window starts at `08:00` and ends at `22:00`.
- If the requested slot is unavailable, the planner searches forward in 15-minute blocks for up to one week.

These rules are simple enough for a university submission but still handle the important scheduling cases.

## Chat Commands

The chat layer supports these command types:

- `move_session`
- `add_session`
- `resize_sessions`
- `delete_session`
- `mark_behind`
- `explain_schedule`

When `OPENAI_API_KEY` is not set, the fallback parser supports common demo phrases such as:

- `Move math to Friday`
- `I am behind on physics`
- `I can only study 30 minutes today`

## Local Storage

By default, saved state is kept outside the repository:

```text
%LOCALAPPDATA%\AdaptiveStudyPlanner
```

Set `STUDY_PLANNER_DATA_DIR` during tests or demos if you want to use a temporary folder.

## Optional Calendar Sync

ICS export works without OAuth credentials. Google and Outlook sync need client credentials in environment variables. If credentials are missing, the status endpoint reports that sync is not configured instead of failing the whole app.

## Running Tests

From the `backend` folder:

```powershell
python -m pytest
```

The tests cover timetable importers, planner behavior, fallback chat parsing, ICS rendering, calendar sync request behavior, and service-level route logic.
