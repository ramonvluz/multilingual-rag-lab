from __future__ import annotations

from dataclasses import dataclass

from multilingual_rag_lab.application.ports import (
    DocumentRepository,
    Embedder,
    KnowledgeStore,
    LLMPort,
)
from multilingual_rag_lab.domain.models import QueryResult, Source


@dataclass(slots=True)
class QueryKnowledge:
    embedder: Embedder
    store: KnowledgeStore
    repository: DocumentRepository
    llm: LLMPort | None
    top_k: int

    def execute(self, question: str) -> QueryResult:
        retrieved = self.store.search(self.embedder.embed([question])[0], self.top_k)
        if not retrieved:
            return QueryResult(
                "I don't have enough evidence to answer this question.", [], [], True
            )
        sources, context_lines = [], []
        for item in retrieved:
            document = self.repository.get(item.chunk.document_id)
            sources.append(
                Source(document.document_id, item.chunk.chunk_id, document.filename, item.score)
            )
            context_lines.append(f"[{item.chunk.chunk_id}]\n{item.chunk.text}")
        if self.llm is None:
            return QueryResult(
                "Generation is not configured; retrieved evidence is available.", sources, [], True
            )
        answer = self.llm.generate(question, "\n\n".join(context_lines))
        cited = [source.chunk_id for source in sources if source.chunk_id in answer]
        return QueryResult(answer, sources, cited, False)
