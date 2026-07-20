.DEFAULT_GOAL := help

.PHONY: help setup test lint format typecheck check

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install the package and development tools
	python -m pip install --upgrade pip
	python -m pip install -e '.[dev]'

test: ## Run the offline test suite with coverage
	python -m pytest

lint: ## Run Ruff lint and formatting checks
	python -m ruff check .
	python -m ruff format --check .

format: ## Apply Ruff formatting and safe lint fixes
	python -m ruff check --fix .
	python -m ruff format .

typecheck: ## Run strict type checking
	python -m mypy

check: lint typecheck test ## Run the complete local quality gate
	python scripts/safety_scan.py
