.PHONY: setup lint format typecheck test integration build up down smoke ingest reindex benchmark
setup:
	uv sync --all-groups
lint:
	uv run ruff check .
format:
	uv run ruff format .
typecheck:
	uv run mypy
test:
	uv run pytest tests/unit tests/api
integration:
	uv run pytest tests/integration
build:
	docker compose build app
up:
	docker compose up -d
down:
	docker compose down
smoke:
	uv run pytest tests/smoke
ingest:
	uv run rag-lab ingest $(FILE)
reindex:
	uv run rag-lab reindex
benchmark:
	uv run rag-lab evaluate $(DATASET)
