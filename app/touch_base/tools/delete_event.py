"""Delete event tool wrapper."""

from app.touch_base.factories import get_calendar_service


def delete_event(
    event_id: str,
    confirm: bool,
) -> dict:
    return get_calendar_service().delete_event(event_id, confirm)
