from __future__ import annotations

from typing import Optional

from app.domain.ports.calendar_repository import CalendarRepository


class CalendarService:
    def __init__(self, repository: CalendarRepository):
        self.repository = repository

    def list_events(self, start_date: str, days: int) -> dict:
        return self.repository.list_events(start_date, days)

    def create_event(
        self, summary: str, start_time: str, end_time: str, attendees: Optional[list[str]] = None
    ) -> dict:
        return self.repository.create_event(summary, start_time, end_time, attendees)

    def edit_event(self, event_id: str, summary: str, start_time: str, end_time: str) -> dict:
        return self.repository.edit_event(event_id, summary, start_time, end_time)

    def delete_event(self, event_id: str, confirm: bool) -> dict:
        return self.repository.delete_event(event_id, confirm)

    def find_free_time(
        self, date: str, duration_minutes: int = 15, emails: Optional[list[str]] = None
    ) -> list:
        return self.repository.find_free_time(date, duration_minutes, emails)
