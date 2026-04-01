from typing import Optional

from app.touch_base.factories import get_docs_service


# =========================
# MAIN SEARCH FUNCTION
# =========================
def search_project_docs(
    query: str,
    top_k: int = 5,
    use_mmr: bool = True,
    score_threshold: Optional[float] = None
) -> str:
    return get_docs_service().search(query, top_k, use_mmr, score_threshold)