# 0001. Self-hosted Docker Compose deployment

- Status: accepted
- Date: 2026-10-06

## Context

Financial data must stay on the household's own hardware; the app has a handful of users.

## Decision

Run every service from one `docker-compose.yml` on the development machine, behind Caddy with internal TLS.

## Alternatives rejected

Cloud hosting (GCP): unnecessary cost and exposure of financial data.

## Consequences

No managed backups: the `backup` service and a tested restore procedure are mandatory (F-ADM-1/2).
