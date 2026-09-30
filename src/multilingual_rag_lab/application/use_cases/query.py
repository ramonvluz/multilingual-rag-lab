from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from multilingual_rag_lab.application.ports import (
    DocumentRepository,
    Embedder,
    KnowledgeStore,
    LLMPort,
)
from multilingual_rag_lab.domain.models import QueryResult, RetrievalMethod, RetrievedChunk, Source


def strip_diacritics(text: str) -> str:
    """Normalize only the supplemental lexical query, preserving case and punctuation."""
    return "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))


@dataclass(slots=True)
class QueryKnowledge:
    embedder: Embedder
    store: KnowledgeStore
    repository: DocumentRepository
    llm: LLMPort | None
    top_k: int

    def execute(self, question: str) -> QueryResult:
        dense = self.store.search(self.embedder.embed([question])[0], self.top_k)
        sparse = self.store.sparse_search(question, self.top_k)
        normalized = strip_diacritics(question)
        sparse_normalized = (
            self.store.sparse_search(normalized, self.top_k) if normalized != question else []
        )
        retrieved: list[tuple[RetrievedChunk, RetrievalMethod]] = []
        seen: set[str] = set()
        branches: tuple[tuple[RetrievalMethod, list[RetrievedChunk]], ...] = (
            ("dense", dense),
            ("sparse_original", sparse),
            ("sparse_normalized", sparse_normalized),
        )
        for method, items in branches:
            for item in items:
                if item.chunk.chunk_id not in seen:
                    seen.add(item.chunk.chunk_id)
                    retrieved.append((item, method))
        if not retrieved:
            return QueryResult(
                "I don't have enough evidence to answer this question.", [], [], True
            )
        sources, context_lines = [], []
        for item, method in retrieved:
            document = self.repository.get(item.chunk.document_id)
            sources.append(
                Source(document.document_id, item.chunk.chunk_id, document.filename, item.score, method)
            )
            context_lines.append(f"[{item.chunk.chunk_id}]\n{item.chunk.text}")
        if self.llm is None:
            return QueryResult(
                "Generation is not configured; retrieved evidence is available.", sources, [], True
            )
        answer = self.llm.generate(question, "\n\n".join(context_lines))
        if answer.strip() == "INSUFFICIENT_EVIDENCE":
            return QueryResult(
                "I don't have enough evidence to answer this question.", sources, [], True
            )
        cited = [source.chunk_id for source in sources if source.chunk_id in answer]
        if not cited:
            return QueryResult(
                "I don't have enough evidence to answer this question.", sources, [], True
            )
        return QueryResult(answer, sources, cited, False)
