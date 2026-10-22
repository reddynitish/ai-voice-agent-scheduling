"""Thin Google Calendar wrapper: OAuth, busy-time lookup, free-slot search, event creation.

Run `uv run python calendar_client.py` once to sign in; it saves token.json.
"""

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
HERE = Path(__file__).parent
TOKEN_FILE = HERE / "token.json"
CREDENTIALS_FILE = HERE / "credentials.json"

TZ = ZoneInfo(os.getenv("TIMEZONE", "America/New_York"))
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
OPEN_HOUR, CLOSE_HOUR = 9, 17  # business hours, Mon-Fri
SLOT_STEP = timedelta(minutes=30)


def _credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    return creds


def _service():
    # googleapiclient services aren't thread-safe; build one per call.
    return build("calendar", "v3", credentials=_credentials(), cache_discovery=False)


def business_window(day: date) -> tuple[datetime, datetime] | None:
    """Opening and closing time for a day, or None if closed (weekends)."""
    if day.weekday() >= 5:
        return None
    return (
        datetime.combine(day, time(OPEN_HOUR), TZ),
        datetime.combine(day, time(CLOSE_HOUR), TZ),
    )


def busy_intervals(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Busy (non-transparent) event intervals overlapping [start, end)."""
    items = (
        _service()
        .events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )
    busy = []
    for ev in items:
        if ev.get("transparency") == "transparent" or ev.get("status") == "cancelled":
            continue
        s, e = ev["start"], ev["end"]
        if "dateTime" in s:
            busy.append((datetime.fromisoformat(s["dateTime"]), datetime.fromisoformat(e["dateTime"])))
        else:  # all-day event blocks the whole day
            busy.append(
                (
                    datetime.combine(date.fromisoformat(s["date"]), time(0), TZ),
                    datetime.combine(date.fromisoformat(e["date"]), time(0), TZ),
                )
            )
    return busy


def free_slots(
    busy: list[tuple[datetime, datetime]],
    window_start: datetime,
    window_end: datetime,
    duration: timedelta,
    not_before: datetime | None = None,
) -> list[datetime]:
    """Start times on a SLOT_STEP grid within the window that don't overlap any busy interval."""
    slots = []
    t = window_start
    while t + duration <= window_end:
        if (not_before is None or t >= not_before) and all(t + duration <= b0 or t >= b1 for b0, b1 in busy):
            slots.append(t)
        t += SLOT_STEP
    return slots


def create_event(
    summary: str,
    start: datetime,
    duration: timedelta,
    description: str = "",
    attendee_email: str | None = None,
) -> dict:
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": str(TZ)},
        "end": {"dateTime": (start + duration).isoformat(), "timeZone": str(TZ)},
    }
    if attendee_email:
        body["attendees"] = [{"email": attendee_email}]
    return (
        _service()
        .events()
        .insert(calendarId=CALENDAR_ID, body=body, sendUpdates="all" if attendee_email else "none")
        .execute()
    )


if __name__ == "__main__":
    _credentials()
    now = datetime.now(TZ)
    print(f"Signed in. {len(busy_intervals(now, now + timedelta(days=7)))} busy events in the next 7 days.")
