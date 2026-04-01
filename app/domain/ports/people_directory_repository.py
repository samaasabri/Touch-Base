from __future__ import annotations

from abc import ABC, abstractmethod


class PeopleDirectoryRepository(ABC):
    @abstractmethod
    def lookup_member(self, name: str) -> dict:
        raise NotImplementedError
