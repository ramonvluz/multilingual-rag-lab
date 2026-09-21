from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from multilingual_rag_lab.bootstrap.composition import Container, build_container
from multilingual_rag_lab.domain.errors import (
    ApplicationError,
    DependencyUnavailable,
    DocumentNotFound,
)

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)


def _document_response(document: Any) -> dict[str, Any]:
    value = asdict(document)
    value["ingested_at"] = document.ingested_at.isoformat()
    return value


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = None
        app.state.startup_error = None
        try:
            app.state.container = build_container()
        except Exception as error:
            app.state.startup_error = error
            logger.warning("dependency_unavailable", extra={"error": type(error).__name__})
        yield

    app = FastAPI(title="Multilingual RAG Lab", version="0.1.0", lifespan=lifespan)

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
        try:
            document, created = container().ingest.execute(file.filename or "", await file.read())
            return {"document": _document_response(document), "created": created}
        except ApplicationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/documents")
    def list_documents() -> list[dict[str, Any]]:
        return [_document_response(item) for item in container().list_documents.execute()]

    @app.delete("/documents/{document_id}", status_code=204)
    def delete(document_id: str) -> None:
        try:
            container().delete.execute(document_id)
        except DocumentNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/query")
    def query(request: QueryRequest) -> dict[str, Any]:
        try:
            return asdict(container().query.execute(request.question))
        except DependencyUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ApplicationError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    return app


app = create_app()
