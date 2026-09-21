from __future__ import annotations

import time

from multilingual_rag_lab.domain.errors import DependencyUnavailable, LLMProviderError


class GeminiAdapter:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key, self.model = api_key, model

    def generate(self, question: str, context: str) -> str:
        if not self.api_key:
            raise DependencyUnavailable("GEMINI_API_KEY is not configured")
        try:
            from google import genai
        except ImportError as error:
            raise DependencyUnavailable("google-genai is unavailable") from error
        prompt = f"""Answer only from the evidence below. If it is insufficient, say so.
Use cited chunk IDs exactly as [chunk_id]; never invent citations.

Evidence:
{context}

Question: {question}"""
        client = genai.Client(api_key=self.api_key)
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=self.model, contents=prompt)
                if not response.text:
                    raise LLMProviderError("Gemini returned an empty response")
                return response.text
            except LLMProviderError:
                raise
            except Exception as error:
                if attempt == 2:
                    raise LLMProviderError("Gemini generation failed") from error
                time.sleep(0.25 * (2**attempt))
        raise LLMProviderError("Gemini generation failed")
