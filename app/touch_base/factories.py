from __future__ import annotations

from functools import lru_cache

from app.application.calendar_service import CalendarService
from app.application.docs_service import DocsService
from app.application.people_service import PeopleService
from app.config import get_settings
from app.infrastructure.calendar.google_calendar_repository import GoogleCalendarRepository
from app.infrastructure.docs.chroma_docs_repository import ChromaDocsRepository
from app.infrastructure.people.file_people_directory_repository import FilePeopleDirectoryRepository


@lru_cache(maxsize=1)
def get_calendar_service() -> CalendarService:
    return CalendarService(GoogleCalendarRepository(get_settings()))


@lru_cache(maxsize=1)
def get_docs_service() -> DocsService:
    return DocsService(ChromaDocsRepository(get_settings()))


@lru_cache(maxsize=1)
def get_people_service() -> PeopleService:
    return PeopleService(FilePeopleDirectoryRepository(get_settings()))
