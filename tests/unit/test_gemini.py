import sys
from types import SimpleNamespace

import pytest

from multilingual_rag_lab.adapters.outbound.llm.gemini import GeminiAdapter


def test_prompt_requires_exact_insufficiency_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    response = " \nINSUFFICIENT_EVIDENCE\n "

    def generate_content(*, model: str, contents: str) -> SimpleNamespace:
        calls.append((model, contents))
        return SimpleNamespace(text=response)

    def client(*, api_key: str) -> SimpleNamespace:
        assert api_key == "unit-test-placeholder"
        return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=SimpleNamespace(Client=client)))
    result = GeminiAdapter("unit-test-placeholder", "fake-model").generate(
        "Question?", "[retrieved-id]\nEvidence text"
    )

    assert result == response  # The adapter must preserve the provider's original response.
    assert len(calls) == 1
    model, prompt = calls[0]
    assert model == "fake-model"
    assert "Answer only from the evidence below." in prompt
    assert "Use retrieved chunk IDs exactly as [chunk_id]; never invent citations." in prompt
    assert (
        "If the evidence is insufficient to answer the question, return exactly:\n"
        "INSUFFICIENT_EVIDENCE\n"
        "In that case return nothing else: no explanation, no additional text, and no citations."
    ) in prompt
    assert "Evidence:\n[retrieved-id]\nEvidence text" in prompt
    assert "Question: Question?" in prompt
