# 0004. PostgreSQL system of record, DuckDB for analytics

- Status: accepted
- Date: 2026-10-06

## Context

Several household members write concurrently; analytics need columnar scans; GenAI may need vectors.

## Decision

PostgreSQL 17 holds all data. DuckDB attaches it read-only and writes Parquet snapshots for analytics.

## Alternatives rejected

SQLite only (concurrency, no pgvector).

## Consequences

Metrics are defined once (SQL views or core functions) to avoid divergent implementations.
