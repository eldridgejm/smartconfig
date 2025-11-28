.PHONY: lint typecheck test coverage checks

checks: lint typecheck test doctest coverage

lint:
	uv run ruff check

typecheck:
	uv run mypy src
	uv run mypy tests/ --check-untyped-defs

test:
	uv run pytest

doctest:
	cd docs && uv run make doctest

coverage:
	uv run pytest --cov=src --cov-report=term-missing
