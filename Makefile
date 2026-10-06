# Single entry point for dev tasks. Node comes from fnm (see .node-version).
SHELL := /bin/bash
# Use the fnm default Node when the shell has not loaded fnm (Claude hooks, cron, …).
export PATH := $(HOME)/.local/share/fnm/aliases/default/bin:$(PATH)
BACKEND := backend
# ops/ scripts run outside the backend image but follow its lint and type rules.
OPS_LINT := uv run ruff format --check --config pyproject.toml ../ops && uv run ruff check --config pyproject.toml ../ops && uv run mypy --strict ../ops/backup/backup.py
FRONTEND := frontend

.PHONY: setup hooks migrate migration dev-api dev-web check check-fast check-backend check-frontend fmt test up down logs openapi

setup: hooks ## Install all dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && pnpm install --frozen-lockfile

hooks: ## Enable the repo git hooks (commit-msg guard)
	git config core.hooksPath .githooks

migrate: ## Apply database migrations (KWAK_DATABASE_URL)
	cd $(BACKEND) && KWAK_ENV=dev uv run alembic upgrade head

migration: ## New migration from model changes: make migration m="add user table"
	cd $(BACKEND) && KWAK_ENV=dev uv run alembic revision --autogenerate -m "$(m)"

openapi: ## Regenerate the TS API client from the backend schema (commit the result)
	cd $(BACKEND) && KWAK_ENV=dev uv run kwak openapi > ../$(FRONTEND)/openapi.json
	cd $(FRONTEND) && pnpm -s openapi

dev-api: ## Run the API with reload on :8000
	cd $(BACKEND) && KWAK_ENV=dev uv run uvicorn kwak_api.main:app --reload --port 8000

dev-web: ## Run the Vite dev server on :5173 (proxies /api to :8000)
	cd $(FRONTEND) && pnpm dev

check: check-backend check-frontend ## Full lint + types + tests (what CI runs)

check-backend:
	cd $(BACKEND) && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest -q
	cd $(BACKEND) && $(OPS_LINT)

check-frontend:
	cd $(FRONTEND) && pnpm check && pnpm typecheck && pnpm test

check-fast: ## Lint + types + unit tests, used by the Claude Stop hook
	cd $(BACKEND) && uv run ruff check -q . && uv run mypy && uv run pytest -q -x -p no:cacheprovider
	cd $(FRONTEND) && pnpm -s check && pnpm -s typecheck && pnpm -s test

fmt: ## Format everything
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .
	cd $(FRONTEND) && pnpm fix

test: ## Tests only
	cd $(BACKEND) && uv run pytest
	cd $(FRONTEND) && pnpm test

up: ## Build and start the full stack (https://localhost:8443)
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f
