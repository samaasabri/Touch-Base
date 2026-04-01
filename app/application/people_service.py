from __future__ import annotations

from app.domain.ports.people_directory_repository import PeopleDirectoryRepository


class PeopleService:
    def __init__(self, repository: PeopleDirectoryRepository):
        self.repository = repository

    def lookup_member(self, name: str) -> dict:
        return self.repository.lookup_member(name)
