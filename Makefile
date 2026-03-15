.PHONY: install test lint fmt check typecheck

install:
	uv sync --all-extras

test:
	uv run pytest --cov --cov-report=term-missing

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy src

fmt:
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: lint typecheck test
