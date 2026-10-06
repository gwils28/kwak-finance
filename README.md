# Kwak Finance

Self-hosted web app to manage a household's budget and net worth: cash accounts, securities, crypto, real estate, loans and use assets. Analytics, forecasting and local GenAI features are planned for later phases.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.13 is fetched automatically)
- Node.js 24 (see `.node-version`, e.g. via [fnm](https://github.com/Schniz/fnm)) and pnpm (`corepack enable`)
- Docker with Compose

## Getting started

```bash
make setup             # install deps + enable git hooks
make dev-api           # API on http://localhost:8000
make dev-web           # UI on http://localhost:5173 (proxies /api)
make check             # lint + types + tests, as in CI
```

Full stack in Docker:

```bash
cp .env.example .env   # then edit the secrets
make up                # https://localhost:8443
docker compose exec api kwak migrate
docker compose exec -it api kwak create-owner --household "Home" --email you@example.com --name "You"
```

`.env` must set `KWAK_ENV=prod` and `KWAK_SECRET_KEY` (from `cd backend && uv run kwak generate-key`). The key encrypts the TOTP secrets: back it up apart from the database backups. If it is lost, every user has to set up TOTP again.

`create-owner` asks for the password (at least 12 characters). At first login, the owner scans a QR code to set up TOTP (mandatory). There is no public sign-up: other members join by invitation.

## Documentation

- [Specifications](docs/SPECIFICATIONS.md)
- [Architecture](docs/ARCHITECTURE.md) and [decision records](docs/adr/)
- [Claude Code usage](docs/CLAUDE_CODE.md)

## Contributing

Single maintainer. Conventional Commits are required and enforced by `.githooks/commit-msg` and CI.

## Corrections to the plan

Deviations from the original specifications are logged here as they happen.
