# Single entry point for dev tasks. Node comes from fnm (see .node-version).
SHELL := /bin/bash
# Use the fnm default Node when the shell has not loaded fnm (Claude hooks, cron, …).
export PATH := $(HOME)/.local/share/fnm/aliases/default/bin:$(PATH)
BACKEND := backend
FRONTEND := frontend

.PHONY: setup hooks dev-api dev-web check check-fast check-backend check-frontend fmt test up down logs openapi

setup: hooks ## Install all dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && pnpm install --frozen-lockfile

hooks: ## Enable the repo git hooks (commit-msg guard)
	git config core.hooksPath .githooks

dev-api: ## Run the API with reload on :8000
	cd $(BACKEND) && uv run uvicorn kwak_api.main:app --reload --port 8000

dev-web: ## Run the Vite dev server on :5173 (proxies /api to :8000)
	cd $(FRONTEND) && pnpm dev

check: check-backend check-frontend ## Full lint + types + tests (what CI runs)

check-backend:
	cd $(BACKEND) && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest -q

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
