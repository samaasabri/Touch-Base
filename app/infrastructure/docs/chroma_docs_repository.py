from __future__ import annotations

from typing import Optional

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_google_vertexai import VertexAIEmbeddings

from app.config import Settings
from app.domain.ports.docs_repository import DocsRepository


class ChromaDocsRepository(DocsRepository):
    def __init__(self, settings: Settings):
        self.settings = settings
        self._vectorstore = None

    def _get_vectorstore(self):
        if self._vectorstore is None:
            if not self.settings.chroma_db_dir.exists():
                raise ValueError("Chroma DB not found. Run ingestion first.")
            embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
            self._vectorstore = Chroma(
                persist_directory=str(self.settings.chroma_db_dir),
                embedding_function=embeddings,
            )
        return self._vectorstore

    def _format_docs(self, docs: list[Document]) -> str:
        formatted = []
        for i, doc in enumerate(docs):
            meta = doc.metadata or {}
            source = meta.get("filename") or meta.get("source", "Unknown")
            formatted.append(f"[Source {i + 1}: {source}]\n{doc.page_content.strip()}")
        return "\n\n".join(formatted)

    def search(
        self, query: str, top_k: int = 5, use_mmr: bool = True, score_threshold: Optional[float] = None
    ) -> str:
        try:
            vectorstore = self._get_vectorstore()
            if use_mmr:
                docs = vectorstore.max_marginal_relevance_search(query, k=top_k, fetch_k=top_k * 3)
            else:
                docs = vectorstore.similarity_search(query, k=top_k)
            if not docs:
                return "No relevant information found."
            if score_threshold is not None:
                docs = [
                    doc
                    for doc, score in vectorstore.similarity_search_with_score(query, k=top_k)
                    if score >= score_threshold
                ]
                if not docs:
                    return "No results passed the relevance threshold."
            return self._format_docs(docs)
        except Exception as e:
            return f"[RAG ERROR] {e}"
