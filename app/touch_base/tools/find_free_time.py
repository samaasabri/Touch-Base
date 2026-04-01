from typing import Optional

from app.touch_base.factories import get_calendar_service


def find_free_time(
    date: str,
    duration_minutes: int = 15,
    emails: Optional[list[str]] = None,
) -> list:
    return get_calendar_service().find_free_time(date, duration_minutes, emails)