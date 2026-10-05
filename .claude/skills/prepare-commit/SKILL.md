---
name: prepare-commit
description: Prepare a commit for the maintainer to run: check the staged diff covers one topic, run checks, and propose a Conventional Commit message. Use when the user asks to commit, prepare a commit, or write a commit/PR message.
---

Claude never runs `git commit` or `git push` in this repo: the maintainer must be the sole GitHub contributor.

1. Run `git status` and `git diff --staged` (if nothing is staged, show `git diff` and propose which files to `git add`, grouped by topic).
2. If the staged diff mixes topics (e.g. a feature and an unrelated refactor), stop and propose how to split it into several commits.
3. Run `make check-fast` and report the result. Do not propose a commit while it fails.
4. Propose the message:
   - Subject: `<type>(<scope>): <imperative summary>`, at most 72 chars. Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert. Scopes: `core`, `api`, `analytics`, `web`, `import`, `infra`, `claude`, `docs`.
   - Body (optional): why the change was made, not what it does line by line.
   - No `Co-Authored-By` trailer, no "Generated with" line.
5. Give the exact command for the maintainer, e.g. `git commit -m "feat(import): parse OFX files" -m "<body>"`.
6. For a PR, propose a title (same format) and a body with: Summary, How it was tested (paste the real output), and Deviations from the plan (if any, also add them to the README section "Corrections to the plan").
