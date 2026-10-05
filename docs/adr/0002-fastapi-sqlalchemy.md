# 0002. FastAPI + SQLAlchemy 2 + Alembic backend

- Status: accepted
- Date: 2026-10-06

## Context

We need a typed Python API whose schema drives the TypeScript client, and the analytics phases are Python.

## Decision

FastAPI with Pydantic v2, SQLAlchemy 2 typed models, Alembic migrations.

## Alternatives rejected

Django + DRF (heavier, admin not needed); Litestar (smaller community).

## Consequences

OpenAPI is the contract between back and front; the TS client is generated.
