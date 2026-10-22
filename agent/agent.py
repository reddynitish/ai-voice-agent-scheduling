import asyncio
import logging
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, TurnHandlingOptions, function_tool, inference

load_dotenv(".env.local")

import calendar_client as cal  # noqa: E402  (reads TIMEZONE/CALENDAR_ID from env)

logger = logging.getLogger("scheduler")

INSTRUCTIONS = """You are Ava, a friendly voice receptionist who books appointments on one calendar.
Today is {today}. The current time is {now}. All times are in the {tz} time zone.
Business hours are Monday to Friday, {open_h} to {close_h}. Appointments default to 30 minutes.

How to handle a booking:
1. Find out what the appointment is for, the preferred day and time, and the caller's name.
   Ask one question at a time. If the caller gives several details at once, don't ask for them again.
   Speech recognition often mishears names. If the caller spells a name, use the spelling exactly.
2. Work out the exact date yourself from relative phrases like "tomorrow" or "next Tuesday", using today's date above.
3. Call check_availability as soon as you know the day and time, before asking anything else. If the time is taken, offer the alternatives it returns.
4. Ask if they'd like a calendar invite by email. This is optional.
   If they give one, read it back once in plain letters without phonetic words, for example "r e d d y at gmail dot com".
5. Once you have everything, confirm ONCE in a single sentence: name, purpose, day, date, and time, plus the email if given.
   Only call book_appointment after the caller says yes. Don't ask for confirmation again after that.
6. After booking, confirm it's done, ask if there's anything else, then say goodbye.

If the caller changes any detail, update it and confirm again. Never make up availability or say something is booked unless book_appointment succeeded.
Don't mention the time zone unless the caller asks.
Speak naturally in short sentences. Say times like "two thirty PM" and dates like "Tuesday, October twenty eighth".
Never use markdown, lists, emojis, or symbols."""


def _parse(day: str, at: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), datetime.strptime(at, "%H:%M").time(), cal.TZ)


def _say(t: datetime) -> str:
    return t.strftime("%A %B %d at %I:%M %p").replace(" 0", " ")


def _alternatives(day: date, duration: timedelta, limit: int = 3) -> list[datetime]:
    """Next free slots starting on `day`, looking up to a week ahead."""
    now = datetime.now(cal.TZ)
    found: list[datetime] = []
    for offset in range(7):
        window = cal.business_window(day + timedelta(days=offset))
        if not window:
            continue
        busy = cal.busy_intervals(*window)
        found += cal.free_slots(busy, *window, duration, not_before=now)
        if len(found) >= limit:
            break
    return found[:limit]


def _check(day: str, at: str | None, duration_minutes: int) -> str:
    duration = timedelta(minutes=duration_minutes)
    try:
        d = date.fromisoformat(day)
        start = _parse(day, at) if at else None
    except ValueError:
        return "Invalid date or time format. Use YYYY-MM-DD and 24-hour HH:MM."

    if start is None:
        slots = _alternatives(d, duration, limit=5)
        return "Open times: " + "; ".join(_say(s) for s in slots) if slots else "No open times in the next week."

    window = cal.business_window(d)
    if start < datetime.now(cal.TZ):
        reason = "That time is in the past."
    elif not window or start < window[0] or start + duration > window[1]:
        reason = "That time is outside business hours."
    elif cal.free_slots(cal.busy_intervals(start, start + duration), start, start + duration, duration):
        return f"{_say(start)} is available."
    else:
        reason = "That time is already booked."
    alts = _alternatives(d, duration)
    return f"{reason} Nearest open times: " + "; ".join(_say(s) for s in alts)


def _book(name: str, day: str, at: str, duration_minutes: int, purpose: str, email: str | None) -> str:
    check = _check(day, at, duration_minutes)
    if not check.endswith("is available."):
        return f"Not booked. {check}"
    start = _parse(day, at)
    event = cal.create_event(
        summary=f"{purpose} - {name}",
        start=start,
        duration=timedelta(minutes=duration_minutes),
        description=f"Booked by voice assistant for {name}.",
        attendee_email=email,
    )
    logger.info("booked event %s", event.get("id"))
    invite = f" An invite was sent to {email}." if email else ""
    return f"Booked: {purpose} for {name} on {_say(start)}.{invite}"


class Scheduler(Agent):
    def __init__(self) -> None:
        now = datetime.now(cal.TZ)
        super().__init__(
            instructions=INSTRUCTIONS.format(
                today=now.strftime("%A, %B %d, %Y"),
                now=now.strftime("%I:%M %p"),
                tz=cal.TZ.key,
                open_h=now.replace(hour=cal.OPEN_HOUR, minute=0).strftime("%I %p").lstrip("0"),
                close_h=now.replace(hour=cal.CLOSE_HOUR, minute=0).strftime("%I %p").lstrip("0"),
            ),
        )

    @function_tool
    async def check_availability(
        self, context: RunContext, date: str, time: str | None = None, duration_minutes: int = 30
    ) -> str:
        """Check whether a time is free, or list open times on a day.

        Args:
            date: Day in YYYY-MM-DD format.
            time: Start time in 24-hour HH:MM format. Omit to list open times that day.
            duration_minutes: Appointment length in minutes.
        """
        return await asyncio.to_thread(_check, date, time, duration_minutes)

    @function_tool
    async def book_appointment(
        self,
        context: RunContext,
        name: str,
        date: str,
        time: str,
        purpose: str,
        duration_minutes: int = 30,
        email: str | None = None,
    ) -> str:
        """Create the calendar event. Only call after the caller has explicitly confirmed all details.

        Args:
            name: Caller's name.
            date: Day in YYYY-MM-DD format.
            time: Start time in 24-hour HH:MM format.
            purpose: Short description of the appointment, e.g. "Haircut" or "Dental checkup".
            duration_minutes: Appointment length in minutes.
            email: Caller's email for a calendar invite, if they gave one.
        """
        try:
            return await asyncio.to_thread(_book, name, date, time, duration_minutes, purpose, email)
        except Exception:
            logger.exception("booking failed")
            return "Booking failed due to a calendar error. Apologize and suggest trying again."


server = AgentServer()


@server.rtc_session(agent_name="scheduler")
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        vad=inference.VAD(),
        turn_handling=TurnHandlingOptions(turn_detection=inference.TurnDetector()),
    )
    await session.start(room=ctx.room, agent=Scheduler())
    await session.generate_reply(instructions="Greet the caller as Ava and ask how you can help.")


if __name__ == "__main__":
    agents.cli.run_app(server)
