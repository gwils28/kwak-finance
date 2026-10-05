# Claude Code Usage Plan

How this repository uses Claude Code extensions. It applies the practices from
https://gwils28.github.io/posts/claude-code-data-science/ :

- `CLAUDE.md` is advisory, so a rule that must always hold becomes a **hook**.
- A procedure needed only occasionally becomes a **skill**.
- A role that needs its own context becomes a **subagent**.
- A request repeated three times becomes a rule, a skill or a hook.

## 1. Sole-contributor policy (Git)

The maintainer must be the only contributor on GitHub. Claude never authors commits.

| Layer | Mechanism | Status |
|---|---|---|
| Settings | `.claude/settings.json`: `attribution.commit = ""`, `attribution.pr = ""`, `includeCoAuthoredBy: false` | done |
| Permissions | `deny`: `git commit`, `git push`, `git rebase`, `git reset --hard`, `gh pr merge` | done |
| Git hook | `.githooks/commit-msg` rejects any `Co-Authored-By` trailer and any message that is not a Conventional Commit (`make hooks`). CI re-runs it on every PR commit | done |
| Skill | `prepare-commit`: reviews the staged diff, checks that it covers a single topic, and proposes a Conventional Commit message. The maintainer runs `git commit` | done |

Workflow: one task per session, then a short branch (`feat/…`, `fix/…`, `chore/…`), then a PR to `main` with CI required, then a squash merge done by the maintainer. One commit covers one topic.

Check once that `git config user.name` / `user.email` match the GitHub account.

## 2. CLAUDE.md files

- Root `CLAUDE.md` (≤ 60 lines): non-obvious commands, project rules with their *why*, pointers to docs.
- Nested `backend/CLAUDE.md` and `frontend/CLAUDE.md`, created once each side exists, for side-specific traps.
- Pruning rule: if Claude ignores a line, remove or shorten lines instead of adding more. Each line must pass the test "would Claude get it wrong without this?".

## 3. Hooks (`.claude/settings.json` + `.claude/hooks/`)

| Event | Matcher | Action | Phase |
|---|---|---|---|
| PreToolUse | `Read\|Edit\|Write` | `guard-paths.sh`: block writes under `data/` (real financial data) and reading secrets | done |
| PreToolUse | `Edit\|Write` | Block edits to Alembic migrations already merged to `main` (a new migration must be added instead) | 1 |
| PreToolUse | `Bash` | `guard-bash.sh`: block git commands with `Co-Authored-By`, `--no-verify` or a `core.hooksPath` change | done |
| PostToolUse | `Edit\|Write` | `format.sh`: ruff on `.py`, Biome on `.ts/.tsx/.css/.json` | done |
| Stop | — | `stop-check.sh`: when backend/frontend code changed, run `make check-fast` and block completion while it fails | done |

## 4. Skills (`.claude/skills/<name>/SKILL.md`)

| Skill | Content | Phase |
|---|---|---|
| `prepare-commit` | Single-topic diff check, Conventional Commit message, PR description template | done |
| `bank-import-profile` | How to add a new bank format: anonymised fixture, test written first, profile, dedup check | 1 |
| `db-migration` | Alembic procedure: autogenerate, review, up/down test on testcontainers, never edit a merged migration | 1 |
| `design-system` | Blog palette tokens, typography, chart colours, shadcn conventions, light/dark check with Chrome | 1 |
| `money-rules` | Decimal handling, sign convention, rounding, domain invariants (spec §8) | 1 |
| `forecast-protocol` | Temporal split, naive baseline, rolling-origin metrics with dispersion, seeds, no look-ahead property test | 4 |
| `simulation-protocol` | Monte Carlo assumptions, versioned parameters, reproducibility | 4 |

## 5. Subagents (`.claude/agents/<name>.md`)

| Agent | Tools | Role | Phase |
|---|---|---|---|
| `code-reviewer` | read-only (Read, Grep, Glob, `git diff`) | Reviews the diff in a fresh context before each PR: correctness, invariants, tests, single topic | done |
| `data-quality` | read-only + Bash for read-only scripts | Inspects imported files and the DB for anomalies (duplicates, gaps, sign errors). Never edits | 1 |
| `security-auditor` | read-only | Reviews the auth, session, CSRF and secrets surface (complements the built-in `/security-review`) | 1 |
| `ui-verifier` | Read + Chrome extension | Checks pages in the browser: theme, contrast, responsive layout, console errors, screenshots | 1 |
| `statistician` | read-only | Reviews the forecasting/simulation protocol and leakage risks. No edits | 4 |
| `ml-engineer` | full edit | Implements features and models in `kwak_analytics` | 4 |

## 6. MCP and external tools

The rule is **CLI before connectors**:

- `gh` for issues and PRs (Claude may draft a PR body; the maintainer merges).
- `psql` against a **read-only** DB role for inspection. No write-capable DB MCP.
- **Claude in Chrome** for UI verification (DOM, screenshots, console).
- An MCP server is added only for structured access that a CLI cannot provide (for example MLflow in phase 4, if adopted).

## 7. Session habits

- Plan mode (`Shift+Tab`) for any multi-file change, with the plan reviewed before editing.
- `/clear` between tasks, and after the same mistake happens twice.
- `/compact <what to keep>` on long sessions.
- "Done" requires evidence: test output, CI link or a screenshot.
- Never delegated to Claude: product and protocol choices, interpretation of results, irreversible operations (deleting data, rewriting history), merging and releases.

## 8. Non-interactive use (later)

`claude -p` in GitHub Actions with restricted tools, for example to draft release notes or run a review comment on PRs. It always runs with read-only tools.
