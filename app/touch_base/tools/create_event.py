"""Create event tool wrapper."""

from typing import Optional

from app.touch_base.factories import get_calendar_service


def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    attendees: Optional[list[str]] = None,
) -> dict:
    return get_calendar_service().create_event(summary, start_time, end_time, attendees)
