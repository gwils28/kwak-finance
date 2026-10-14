---
name: ui-preview
description: Start a throwaway Kwak Finance (fake database, synthetic data, dev servers) to show or check a change in Chrome without touching the real data or the maintainer's session. Use before any browser check of an unmerged change.
---

The Docker stack on https://localhost:8443 runs the merged code on the real data: never point a preview at it, never migrate it, never log into it from Chrome.

## Start

1. **Database** (a container of its own, removed at the end):
   ```bash
   docker run --rm -d --name kwak-preview -e POSTGRES_USER=kwak -e POSTGRES_PASSWORD=kwak -p 55432:5432 postgres:17-alpine
   export KWAK_DATABASE_URL=postgresql+psycopg://kwak:kwak@localhost:55432/kwak KWAK_ENV=dev
   cd backend && uv run kwak migrate
   ```
2. **Owner and data** with a Python script in the scratchpad (never in the repo):
   - create the owner with `kwak_api.cli.main([...create-owner...], read_password=lambda _: pw)`, with a random password;
   - seed synthetic accounts, transactions, plans… through FastAPI's `TestClient(app, base_url="https://localhost")` (Secure cookies need https), logging in, enrolling TOTP (`/api/auth/totp/setup` then `/confirm`) and sending the `X-CSRF-Token` header on writes;
   - for data in the past (plans freeze their targets after the first month), override `app.dependency_overrides[kwak_api.deps.get_now]` while seeding;
   - write the email, password and TOTP secret to `~/.cache/kwak-preview/credentials` (mode 600). Never print them in the conversation. A login code is `kwak_core.totp.hotp(secret, int(time.time()) // 30)`.
3. **Servers**, in the background:
   - API: `cd backend && uv run uvicorn kwak_api.main:app --port 8000` with the same environment. Without `--reload`, so restart it after a backend change.
   - Web: `cd frontend && pnpm dev` (run `eval "$(fnm env)"` first if pnpm is missing). After `make openapi`, restart it with `--force` if a new export is reported missing.
4. **Open http://127.0.0.1:5173, not localhost.** Cookies are scoped by host, not port: a login on `localhost` would overwrite the maintainer's real session on :8443.

Frontend-only change with no new endpoint: skip steps 1 to 3 and point a scratch Vite config's `/api` proxy at `https://localhost:8443` (`secure: false`), then let the maintainer log in themselves. Never type their credentials.

## Stop

Stop uvicorn and Vite, `docker stop kwak-preview`, and delete `~/.cache/kwak-preview`.
