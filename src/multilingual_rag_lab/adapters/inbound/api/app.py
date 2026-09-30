from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from importlib.metadata import version
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from multilingual_rag_lab.bootstrap.composition import Container, build_container
from multilingual_rag_lab.domain.errors import (
    ApplicationError,
    DependencyUnavailable,
    DocumentCorrupt,
    DocumentNotFound,
    IndexIncompatible,
    IndexNotReady,
    IngestionFailed,
    LLMProviderError,
    MutationBusy,
    UnsupportedDocument,
)
from multilingual_rag_lab.domain.models import QueryResult

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value


def _document_response(document: Any) -> dict[str, Any]:
    value = asdict(document)
    value["ingested_at"] = document.ingested_at.isoformat()
    return value


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = None
        try:
            app.state.container = build_container()
        except Exception as error:
            logger.warning("dependency_unavailable", extra={"error": type(error).__name__})
        yield

    app = FastAPI(
        title="Multilingual RAG Lab", version=version("multilingual-rag-lab"), lifespan=lifespan
    )

    @app.exception_handler(ApplicationError)
    async def application_error(request: Request, error: ApplicationError) -> JSONResponse:
        # Static messages keep internal details and exception causes out of the public API.
        mappings = (
            (DocumentNotFound, 404, "Document was not found"),
            (UnsupportedDocument, 400, "Unsupported or unsafe filename"),
            (MutationBusy, 409, "Another mutation is running; retry later"),
            (DependencyUnavailable, 503, "Service dependency is unavailable"),
            (IndexNotReady, 503, "Index is not ready"),
            (IndexIncompatible, 503, "Index configuration is incompatible"),
            (LLMProviderError, 502, "Generation provider failed"),
            (DocumentCorrupt, 500, "Stored document is corrupt; explicit recovery required"),
            (IngestionFailed, 500, "Document ingestion failed"),
        )
        for error_type, status, detail in mappings:
            if isinstance(error, error_type):
                return JSONResponse(status_code=status, content={"detail": detail})
        return JSONResponse(status_code=500, content={"detail": "Internal application error"})

    @app.middleware("http")
    async def request_id(request: Request, call_next: Any) -> Any:
        token, started = request.headers.get("X-Request-ID", str(uuid.uuid4())), time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = token
        logger.info(
            "http_request_completed",
            extra={
                "request_id": token,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            },
        )
        return response

    def container() -> Container:
        value: Container | None = app.state.container
        if value is None:
            raise HTTPException(status_code=503, detail="Service dependency is unavailable")
        return value

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        value = container()
        if not value.store.is_available():
            raise HTTPException(status_code=503, detail="Qdrant is unavailable")
        return {"status": "ready"}

    @app.post("/documents", status_code=201)
    async def ingest(file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
        value = container()
        content = await file.read(value.settings.upload_max_size + 1)
        if not content:
            raise HTTPException(status_code=400, detail="Upload is empty")
        if len(content) > value.settings.upload_max_size:
            raise HTTPException(status_code=413, detail="Upload exceeds configured limit")
        document, created = await run_in_threadpool(
            value.ingest.execute, file.filename or "", content
        )
        return {"document": _document_response(document), "created": created}

    @app.get("/documents")
    def list_documents() -> list[dict[str, Any]]:
        return [_document_response(item) for item in container().list_documents.execute()]

    @app.delete("/documents/{document_id}", status_code=204)
    def delete(document_id: str) -> None:
        container().delete.execute(document_id)

    @app.post("/query", response_model=QueryResult)
    def query(request: QueryRequest) -> QueryResult:
        return container().query.execute(request.question)

    return app


app = create_app()
