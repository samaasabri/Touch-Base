from __future__ import annotations

from typing import Optional

from app.domain.ports.docs_repository import DocsRepository


class DocsService:
    def __init__(self, repository: DocsRepository):
        self.repository = repository

    def search(
        self, query: str, top_k: int = 5, use_mmr: bool = True, score_threshold: Optional[float] = None
    ) -> str:
        return self.repository.search(query, top_k, use_mmr, score_threshold)
