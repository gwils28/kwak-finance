# 0005. EUR-only domain

- Status: accepted
- Date: 2026-10-06

## Context

All accounts are in EUR; full multi-currency ledgers add a lot of complexity.

## Decision

Amounts, budgets and balances are EUR. Foreign-quoted securities store an ECB FX rate per price point, used only for valuation.

## Alternatives rejected

Full multi-currency ledger.

## Consequences

FX history becomes a market-data input alongside prices.
