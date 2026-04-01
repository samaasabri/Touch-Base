"""List events tool wrapper."""

from app.touch_base.factories import get_calendar_service


def list_events(
    start_date: str,
    days: int,
) -> dict:
    return get_calendar_service().list_events(start_date, days)
