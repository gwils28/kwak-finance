---
name: feature-slice
description: Build a feature end to end in Kwak Finance, from the core rule to the screen, the guide and the ship command. Use when implementing a feature or a user-visible change that spans core, API and web.
---

The order below is the one every feature PR followed (#70 → #73). Skip the steps a change does not touch, but never reorder them: each one feeds the next.

1. **Spec.** Find the feature in `docs/SPECIFICATIONS.md` (F-xxx id, §8 invariants). If the behaviour is not written down, or a product choice is open, ask the maintainer before coding and update the spec in the same PR.
2. **Core rule** in `backend/packages/core/src/kwak_core/<topic>.py`: pure functions, no I/O, `Decimal` money (negative = outflow), dates passed in, never read from the clock.
   - Test first in `backend/tests/core/test_<topic>.py`; run it and check it fails for the right reason.
   - An invariant of §8 gets a hypothesis property test.
3. **Schema**, if needed: follow the `db-migration` skill.
4. **API** in `kwak_api/`: the service in `services/<topic>.py` (queries + core calls), the router in `<topic>/routes.py` (thin: parse, authorise, call the service), registered in `main.py`.
   - Every query is scoped to the caller's household, and account data goes through `services.accounts.visible_accounts` / `find_visible_account` (private accounts stay their owner's).
   - Endpoints use `CurrentSession`; time comes from the `Now` dependency so tests can freeze it.
   - Tests in `backend/tests/api/<topic>/` on the real Postgres fixtures, including a test that another member or household gets a 404.
5. **Client.** `make openapi`, then use only the generated functions from `frontend/src/api/generated` (never hand-edit them).
6. **Web** in `frontend/src/<topic>/`:
   - Strings in `frontend/src/i18n/<topic>.ts` (`<topic>En`, `<topic>Fr: typeof <topic>En`), wired in `en.ts` / `fr.ts`. No inline text, no ad-hoc hex: palette tokens only.
   - Amounts and dates through `lib/money.ts` / `lib/dates.ts`.
   - Vitest tests next to the page (`<topic>.test.tsx`), in both languages for anything formatted.
   - New pages go in `router.tsx` and, if top level, in the header.
7. **Guides.** Update `frontend/src/i18n/guide.ts` (the section for the page and, if a new step matters for a new household, the "Getting started" checklist in `guide/GettingStarted.tsx`) in EN and FR, and `guide/guide.test.tsx` if a section was added. If the change touches how the app is run, update `runGuide.ts` too. The `stop-guides.sh` hook reminds you.
8. **Check.** `make check` must pass. For UI changes, ask the `ui-verifier` subagent for a verdict; for auth, session, invite or visibility changes, ask `security-auditor`. Then `code-reviewer` on the full diff.
9. **Ship.** Propose a Conventional Commit subject and a body explaining why (see `prepare-commit`), then end with the one command the maintainer runs, listing only this topic's paths:
   ```bash
   scripts/ship-pr.sh "feat(<scope>): <summary>" "<body>" backend/ frontend/ docs/SPECIFICATIONS.md
   ```

Splitting: a large feature ships as several PRs in this order, each green on its own: `feat(core)`, then `feat(api)` (with migration and `make openapi`), then `feat(web)` (with the guide).
