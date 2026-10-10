# Horizon — developer tasks. Run `make help` for the list.
.DEFAULT_GOAL := help

PY ?= python
VENV ?= .venv

.PHONY: help install dev run cli lint fmt test test-cov docker-build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime dependencies
	$(PY) -m pip install -r requirements.txt

dev: ## Install runtime + dev dependencies (editable)
	$(PY) -m pip install -e ".[dev]"

run: ## Run the web app locally
	$(PY) -m uvicorn horizon.main:app --reload

cli: ## Ask the CLI for today's window (override CITY=...)
	$(PY) -m horizon.cli --city "$(or $(CITY),Hyderabad)"

lint: ## Lint + check formatting
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt: ## Auto-format the code
	$(PY) -m ruff format .
	$(PY) -m ruff check . --fix

test: ## Run the offline test suite
	$(PY) -m pytest

test-cov: ## Run tests with a coverage report
	$(PY) -m pytest --cov=horizon --cov-report=term-missing

docker-build: ## Build the container image
	docker build -t horizon:local .

clean: ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
