# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Kwak Finance — self-hosted household budget and net-worth web app. FastAPI + PostgreSQL backend (uv workspace), React + TypeScript frontend, DuckDB analytics later. Currently in **phase 0** (skeleton: health endpoint, money parsing, themed shell).

- Specs and roadmap: `docs/SPECIFICATIONS.md`
- Architecture, stack, repo layout: `docs/ARCHITECTURE.md`
- Hooks, skills and subagents plan: `docs/CLAUDE_CODE.md`

## Commands

- `make check` — everything CI runs (ruff, mypy strict, pytest, Biome, tsc, Vitest). `make check-fast` is what the Stop hook runs.
- `make dev-api` / `make dev-web` — API on :8000, Vite on :5173 (proxies `/api`).
- Single backend test: `cd backend && uv run pytest tests/core/test_money.py::test_quantize_rounds_half_up_to_cents`
- Single frontend test: `cd frontend && pnpm vitest run src/App.test.tsx -t "unreachable"`
- Node comes from fnm (`~/.local/share/fnm`); if `pnpm` is not found, run `eval "$(fnm env)"`.
- Backend commands run from `backend/` (uv workspace root), frontend ones from `frontend/`.

## Rules

- **Never commit or push.** The maintainer must be the sole GitHub contributor. Prepare the change and propose a Conventional Commit message (`feat:`, `fix:`, `chore:`…). One topic per commit. Never add a `Co-Authored-By` trailer.
- Everything in English: code, docs, UI strings, commit messages.
- Money is `Decimal` / `NUMERIC`, never float. Negative = outflow. EUR only.
- Business rules go in `backend/packages/core` (pure, no I/O) and are tested there, including hypothesis property tests for the invariants in `docs/SPECIFICATIONS.md` §8.
- Write the failing test first, check it fails for the right reason, then implement.
- `data/` holds real financial data: never read it into the conversation unless asked, and never write to it. Test fixtures must be synthetic.
- The TS API client is generated from the FastAPI OpenAPI schema into `frontend/src/api/generated` by `make openapi` (run it after any API change; CI fails on drift). Do not hand-edit it.
- UI colours come from the blog palette tokens (`docs/SPECIFICATIONS.md` §7). Do not introduce ad-hoc hex values.
