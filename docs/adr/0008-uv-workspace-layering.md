# 0008. uv workspace with core / api / analytics packages

- Status: accepted
- Date: 2026-10-06

## Context

Business rules must be testable without I/O, and analytics dependencies should not bloat the API.

## Decision

`kwak_core` (pure, no I/O), `kwak_api` and `kwak_analytics` both depend on core.

## Alternatives rejected

Single package.

## Consequences

Import direction is enforced: core never imports api or analytics.
