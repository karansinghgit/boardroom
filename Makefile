.DEFAULT_GOAL := help
VENV := .venv
PY := $(VENV)/bin/python

.PHONY: help install lint format typecheck test evals check api web debate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create the venv and install the package with all extras
	python3 -m venv $(VENV)
	$(PY) -m pip install -e ".[mcp,web,dev]"

lint: ## Lint with ruff
	$(VENV)/bin/ruff check .

format: ## Format with ruff
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

typecheck: ## Type-check the engine with mypy
	$(VENV)/bin/mypy

test: ## Run the unit and integration tests
	$(PY) -m pytest

evals: ## Run the offline eval report
	$(PY) -m evals.report

check: lint typecheck test ## Run lint, types, and tests

api: ## Run the Django API on port 8000
	$(PY) server/manage.py runserver 8000

web: ## Run the front end dev server
	cd frontend && pnpm dev

debate: ## Run a debate from the CLI, e.g. make debate TICKER=AAPL
	$(VENV)/bin/boardroom debate $(TICKER)
