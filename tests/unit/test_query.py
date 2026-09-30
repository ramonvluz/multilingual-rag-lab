import pytest

from multilingual_rag_lab.application.use_cases.query import QueryKnowledge, strip_diacritics
from multilingual_rag_lab.domain.models import Chunk, Document, RetrievedChunk, Source


class Embedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0]]


class EmptyStore:
    def search(self, vector: list[float], limit: int) -> list[RetrievedChunk]:
        return []

    def sparse_search(self, query: str, limit: int) -> list[RetrievedChunk]:
        return []


class Repository:
    def get(self, document_id: str) -> Document:
        return Document(document_id, document_id, "fixture.md", "md")


CHUNKS = [Chunk.create("fixture", i, f"Evidence {i}") for i in range(2)]
INVENTED_ID = Chunk.create("not-retrieved", 0, "Invented evidence").chunk_id
SOURCES = [Source("fixture", chunk.chunk_id, "fixture.md", 1.0) for chunk in CHUNKS]


class EvidenceStore:
    def __init__(
        self,
        dense: list[RetrievedChunk] | None = None,
        sparse: list[RetrievedChunk] | None = None,
    ) -> None:
        self.dense = [RetrievedChunk(CHUNKS[0], 1.0)] if dense is None else dense
        self.sparse = [RetrievedChunk(CHUNKS[1], 1.0)] if sparse is None else sparse
        self.sparse_by_query: dict[str, list[RetrievedChunk]] = {}
        self.dense_calls: list[tuple[list[float], int]] = []
        self.sparse_calls: list[tuple[str, int]] = []

    def search(self, vector: list[float], limit: int) -> list[RetrievedChunk]:
        self.dense_calls.append((vector, limit))
        return self.dense[:limit]

    def sparse_search(self, query: str, limit: int) -> list[RetrievedChunk]:
        self.sparse_calls.append((query, limit))
        return self.sparse_by_query.get(query, self.sparse)[:limit]


class LLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def generate(self, question: str, context: str) -> str:
        self.calls.append((question, context))
        return self.answer


def test_no_retrieval_explicitly_abstains() -> None:
    result = QueryKnowledge(Embedder(), EmptyStore(), Repository(), None, 5).execute("Pergunta")
    assert result.abstained and not result.sources


@pytest.mark.parametrize(
    "answer,cited",
    [
        (f"Supported answer [{CHUNKS[0].chunk_id}]", [CHUNKS[0].chunk_id]),
        ("Unsupported answer without citations.", []),
        (f"Unsupported answer [{INVENTED_ID}]", []),
        (f"Answer [{CHUNKS[0].chunk_id}] [{INVENTED_ID}]", [CHUNKS[0].chunk_id]),
        (f"Sparse answer [{CHUNKS[1].chunk_id}]", [CHUNKS[1].chunk_id]),
        (f"Answer [{CHUNKS[1].chunk_id}] [{INVENTED_ID}]", [CHUNKS[1].chunk_id]),
        ("INSUFFICIENT_EVIDENCE", []),
        (" \n\tINSUFFICIENT_EVIDENCE\r\n ", []),
        (f" \nSupported answer [{CHUNKS[0].chunk_id}]\t ", [CHUNKS[0].chunk_id]),
        (f"INSUFFICIENT_EVIDENCE is a sentinel [{CHUNKS[0].chunk_id}]", [CHUNKS[0].chunk_id]),
        ("", []),
    ],
    ids=[
        "valid", "uncited", "invented", "mixed", "sparse-valid", "sparse-mixed",
        "sentinel", "sentinel-whitespace", "valid-whitespace", "not-exact-sentinel", "empty",
    ],
)
def test_generation_requires_at_least_one_retrieved_citation(
    answer: str, cited: list[str]
) -> None:
    llm = LLM(answer)
    result = QueryKnowledge(Embedder(), EvidenceStore(), Repository(), llm, 5).execute("Pergunta")
    assert result.sources == SOURCES  # Keep even retrieved chunks not cited by the model.
    assert result.cited_chunk_ids == cited
    assert result.abstained is (not cited)
    if cited:
        assert result.answer == answer
    else:
        assert result.answer == "I don't have enough evidence to answer this question."
        assert result.answer != answer  # Never expose the non-grounded generation as the answer.
    expected_context = "\n\n".join(f"[{chunk.chunk_id}]\n{chunk.text}" for chunk in CHUNKS)
    assert llm.calls == [("Pergunta", expected_context)]


def test_union_preserves_dense_order_and_first_occurrence_without_truncating() -> None:
    sparse_only = Chunk.create("fixture", 2, "Sparse-only evidence")
    store = EvidenceStore(
        dense=[RetrievedChunk(CHUNKS[1], 0.4), RetrievedChunk(CHUNKS[0], 0.2)],
        sparse=[RetrievedChunk(CHUNKS[1], 99.0), RetrievedChunk(sparse_only, 5.0)],
    )
    llm = LLM(f"Answer [{sparse_only.chunk_id}]")
    result = QueryKnowledge(Embedder(), store, Repository(), llm, 2).execute("Pergunta original")

    assert store.dense_calls == [([1.0], 2)]
    assert store.sparse_calls == [("Pergunta original", 2)]
    expected_chunks = [CHUNKS[1], CHUNKS[0], sparse_only]
    assert [source.chunk_id for source in result.sources] == [
        chunk.chunk_id for chunk in expected_chunks
    ]
    assert [source.score for source in result.sources] == [0.4, 0.2, 5.0]
    expected_context = "\n\n".join(f"[{chunk.chunk_id}]\n{chunk.text}" for chunk in expected_chunks)
    assert llm.calls == [("Pergunta original", expected_context)]
    assert result.cited_chunk_ids == [sparse_only.chunk_id]
    assert not result.abstained


def test_sparse_evidence_is_used_even_when_dense_is_empty() -> None:
    llm = LLM(f"Answer [{CHUNKS[1].chunk_id}]")
    result = QueryKnowledge(Embedder(), EvidenceStore(dense=[]), Repository(), llm, 5).execute(
        "Pergunta"
    )
    assert result.sources == [SOURCES[1]]
    assert llm.calls == [("Pergunta", f"[{CHUNKS[1].chunk_id}]\n{CHUNKS[1].text}")]
    assert result.cited_chunk_ids == [CHUNKS[1].chunk_id]
    assert not result.abstained


@pytest.mark.parametrize(
    "original,expected",
    [
        ("JÁ entrou? AÇÃO!", "JA entrou? ACAO!"),
        ("Cafe\u0301?", "Cafe?"),
        ("Query WITHOUT accents?!", "Query WITHOUT accents?!"),
        ("\ufb01cha", "ficha"),  # Compatibility decomposition must use NFKD, not NFD.
    ],
)
def test_strip_diacritics_uses_nfkd_preserving_case_and_punctuation(
    original: str, expected: str
) -> None:
    assert strip_diacritics(original) == expected


def test_supplemental_sparse_preserves_original_query_and_three_branch_union() -> None:
    question = "O evento JÁ entrou?"
    normalized = "O evento JA entrou?"
    normalized_only = Chunk.create("fixture", 2, "Normalized-only evidence")
    store = EvidenceStore(
        dense=[RetrievedChunk(CHUNKS[0], 0.4)],
        sparse=[RetrievedChunk(CHUNKS[0], 99.0), RetrievedChunk(CHUNKS[1], 0.7)],
    )
    store.sparse_by_query[normalized] = [
        RetrievedChunk(CHUNKS[0], 50.0),
        RetrievedChunk(CHUNKS[1], 20.0),
        RetrievedChunk(normalized_only, 0.8),
    ]
    embedder = Embedder()
    llm = LLM(f"Answer [{normalized_only.chunk_id}]")
    result = QueryKnowledge(embedder, store, Repository(), llm, 3).execute(question)

    assert embedder.calls == [[question]]
    assert store.dense_calls == [([1.0], 3)]
    assert store.sparse_calls == [(question, 3), (normalized, 3)]
    expected_chunks = [*CHUNKS, normalized_only]
    assert [source.chunk_id for source in result.sources] == [
        chunk.chunk_id for chunk in expected_chunks
    ]
    assert [source.score for source in result.sources] == [0.4, 0.7, 0.8]
    expected_context = "\n\n".join(f"[{chunk.chunk_id}]\n{chunk.text}" for chunk in expected_chunks)
    assert llm.calls == [(question, expected_context)]
    assert result.cited_chunk_ids == [normalized_only.chunk_id]
    assert result.answer == llm.answer
    assert not result.abstained


def test_missing_llm_keeps_existing_abstention_and_sources() -> None:
    result = QueryKnowledge(Embedder(), EvidenceStore(), Repository(), None, 5).execute("Pergunta")
    assert result.abstained
    assert result.answer == "Generation is not configured; retrieved evidence is available."
    assert result.sources == SOURCES
    assert result.cited_chunk_ids == []


def test_missing_evidence_does_not_call_llm() -> None:
    llm = LLM("Must not be generated")
    result = QueryKnowledge(Embedder(), EmptyStore(), Repository(), llm, 5).execute("Pergunta")
    assert result.abstained
    assert result.answer == "I don't have enough evidence to answer this question."
    assert result.sources == result.cited_chunk_ids == []
    assert llm.calls == []
