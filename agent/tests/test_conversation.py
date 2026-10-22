"""Conversation tests: run Ava in text mode against a real LLM with a fake calendar.

They call LiveKit Inference, so they need LIVEKIT_* credentials in .env.local and are
skipped otherwise. Run with: uv run pytest tests/test_conversation.py
"""

import os
from datetime import date, datetime, time, timedelta

import pytest
from dotenv import load_dotenv

from livekit.agents import AgentSession, inference
from livekit.agents.voice.run_result import FunctionCallEvent

load_dotenv(".env.local")

import agent  # noqa: E402
import calendar_client as cal  # noqa: E402

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.getenv("LIVEKIT_API_KEY"), reason="needs LiveKit credentials"),
]


def next_weekday(weekday: int) -> date:
    """Next given weekday (Mon=0) strictly after today."""
    today = datetime.now(cal.TZ).date()
    return today + timedelta(days=(weekday - today.weekday() - 1) % 7 + 1)


@pytest.fixture
def fake_calendar(monkeypatch):
    state = {"busy": [], "created": []}
    monkeypatch.setattr(cal, "busy_intervals", lambda start, end: list(state["busy"]))

    def create_event(summary, start, duration, description="", attendee_email=None):
        state["created"].append({"summary": summary, "start": start, "attendee": attendee_email})
        return {"id": "test-event"}

    monkeypatch.setattr(cal, "create_event", create_event)
    return state


def booked(result) -> bool:
    return any(
        isinstance(e, FunctionCallEvent) and e.item.name == "book_appointment" for e in result.events
    )


async def test_books_only_after_confirmation(fake_calendar):
    tuesday = next_weekday(1)
    async with inference.LLM(model=agent.LLM_MODEL) as llm, AgentSession(llm=llm) as session:
        await session.start(agent.Scheduler())

        result = await session.run(
            user_input="Hi, I'd like to book a haircut next Tuesday at 2 PM. My name is Nitish, "
            "N I T I S H. No email invite needed."
        )
        result.expect.contains_function_call(name="check_availability")
        assert not booked(result), "booked before the caller confirmed"
        await result.expect[-1].is_message(role="assistant").judge(
            llm, intent="Asks the caller to confirm booking the haircut on Tuesday at 2 PM."
        )

        result = await session.run(user_input="Yes, that's right.")
        result.expect.contains_function_call(name="book_appointment")

    assert len(fake_calendar["created"]) == 1
    event = fake_calendar["created"][0]
    assert event["start"] == datetime.combine(tuesday, time(14), cal.TZ)
    assert "Nitish" in event["summary"]


async def test_offers_alternatives_when_slot_is_taken(fake_calendar):
    wednesday = next_weekday(2)
    taken = datetime.combine(wednesday, time(10), cal.TZ)
    fake_calendar["busy"] = [(taken, taken + timedelta(hours=1))]

    async with inference.LLM(model=agent.LLM_MODEL) as llm, AgentSession(llm=llm) as session:
        await session.start(agent.Scheduler())
        result = await session.run(user_input="Can I get a dental checkup next Wednesday at 10 AM?")

        result.expect.contains_function_call(name="check_availability")
        assert not booked(result)
        await result.expect[-1].is_message(role="assistant").judge(
            llm, intent="Says 10 AM is not available and offers one or more other times."
        )


async def test_does_not_book_outside_business_hours(fake_calendar):
    async with inference.LLM(model=agent.LLM_MODEL) as llm, AgentSession(llm=llm) as session:
        await session.start(agent.Scheduler())
        result = await session.run(
            user_input="Book a meeting for Sam this Saturday at 9 PM. Yes, I confirm, go ahead and book it."
        )
        assert not fake_calendar["created"]
        await result.expect[-1].is_message(role="assistant").judge(
            llm, intent="Explains that time is unavailable or outside business hours and suggests another time."
        )
