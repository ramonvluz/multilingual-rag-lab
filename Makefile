.PHONY: setup lint format typecheck test integration build up down smoke ingest ingest-corpus validate-corpus reindex benchmark
setup:
	uv sync --locked --all-groups
lint:
	uv run ruff check .
format:
	uv run ruff format .
typecheck:
	uv run mypy
test:
	uv run pytest
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
	docker compose exec app rag-lab ingest $(FILE)
validate-corpus:
	uv run rag-lab validate-corpus data/corpus/v1.0.0
ingest-corpus:
	docker compose exec app rag-lab ingest-corpus /app/data/corpus/v1.0.0
reindex:
	docker compose exec app rag-lab reindex
benchmark:
	@test "$(CONFIRM_BENCHMARK)" = "yes" || (echo "Official A/B/C requires explicit authorization: CONFIRM_BENCHMARK=yes"; exit 1)
	docker compose run --rm -v ./evaluation:/app/evaluation app rag-lab evaluate /app/evaluation/datasets/golden_v1.jsonl $(if $(OUTPUT),--output "$(OUTPUT)",)
