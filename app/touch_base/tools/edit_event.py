"""Edit event tool wrapper."""

from app.touch_base.factories import get_calendar_service


def edit_event(
    event_id: str,
    summary: str,
    start_time: str,
    end_time: str,
) -> dict:
    return get_calendar_service().edit_event(event_id, summary, start_time, end_time)
