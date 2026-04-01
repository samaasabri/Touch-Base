from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CalendarRepository(ABC):
    @abstractmethod
    def list_events(self, start_date: str, days: int) -> dict:
        raise NotImplementedError

    @abstractmethod
    def create_event(
        self, summary: str, start_time: str, end_time: str, attendees: Optional[list[str]]
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def edit_event(self, event_id: str, summary: str, start_time: str, end_time: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def delete_event(self, event_id: str, confirm: bool) -> dict:
        raise NotImplementedError

    @abstractmethod
    def find_free_time(
        self, date: str, duration_minutes: int = 15, emails: Optional[list[str]] = None
    ) -> list:
        raise NotImplementedError
