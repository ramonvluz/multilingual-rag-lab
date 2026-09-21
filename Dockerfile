FROM ghcr.io/astral-sh/uv:0.9.27 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/.cache/huggingface PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser && chown appuser:appuser /app
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md ./
COPY --chown=appuser:appuser src ./src
USER appuser
RUN uv sync --locked --no-dev
EXPOSE 8000
CMD ["uvicorn", "multilingual_rag_lab.adapters.inbound.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
