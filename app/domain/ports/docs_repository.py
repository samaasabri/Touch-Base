from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class DocsRepository(ABC):
    @abstractmethod
    def search(
        self, query: str, top_k: int = 5, use_mmr: bool = True, score_threshold: Optional[float] = None
    ) -> str:
        raise NotImplementedError
