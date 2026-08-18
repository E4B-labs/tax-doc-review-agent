.PHONY: install test lint typecheck run redis-up

install:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check .

typecheck:
	uv run mypy app mcp_server

run:
	uv run uvicorn app.main:app --reload

redis-up:
	docker compose up -d redis

