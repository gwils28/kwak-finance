# 0006. Server-side cookie sessions with mandatory TOTP

- Status: accepted
- Date: 2026-10-06

## Context

Same-origin SPA, few users, revocation must be immediate.

## Decision

argon2id passwords, server-side sessions in an httpOnly SameSite cookie, CSRF token, mandatory TOTP with recovery codes.

## Alternatives rejected

JWT (hard to revoke, not needed same-origin); external IdP (overkill self-hosted).

## Consequences

A sessions table and a CSRF middleware are needed in phase 1.
