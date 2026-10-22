from datetime import date, datetime, timedelta

import calendar_client as cal


def at(h: int, m: int = 0) -> datetime:
    return datetime(2026, 10, 27, h, m, tzinfo=cal.TZ)  # a Tuesday


def test_free_slots_skip_busy_and_respect_duration():
    busy = [(at(10), at(11)), (at(13, 30), at(14))]
    slots = cal.free_slots(busy, at(9), at(15), timedelta(minutes=60))
    assert slots == [at(9), at(11), at(11, 30), at(12), at(12, 30), at(14)]


def test_free_slots_not_before():
    slots = cal.free_slots([], at(9), at(11), timedelta(minutes=30), not_before=at(10))
    assert slots == [at(10), at(10, 30)]


def test_weekends_closed():
    assert cal.business_window(date(2026, 10, 24)) is None  # Saturday
    assert cal.business_window(date(2026, 10, 27)) == (at(9), at(17))
