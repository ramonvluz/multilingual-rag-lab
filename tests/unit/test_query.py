from multilingual_rag_lab.application.use_cases.query import QueryKnowledge
from multilingual_rag_lab.domain.models import Document, RetrievedChunk


class Embedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0]]


class EmptyStore:
    def search(self, vector: list[float], limit: int) -> list[RetrievedChunk]:
        return []


class Repository:
    def get(self, document_id: str) -> Document:
        return Document(document_id, document_id, "fixture.md", "md")


def test_no_retrieval_explicitly_abstains() -> None:
    result = QueryKnowledge(Embedder(), EmptyStore(), Repository(), None, 5).execute("Pergunta")
    assert result.abstained and not result.sources
