#!/usr/bin/env bash
# Stop: refuse to finish while code changes leave lint/types/tests red.
set -uo pipefail
input=$(cat)
[[ "$(jq -r '.stop_hook_active' <<<"$input")" == "true" ]] && exit 0
cd "$CLAUDE_PROJECT_DIR"
git status --porcelain --untracked-files=all -- backend frontend | grep -qE '\.(py|ts|tsx|css)$' || exit 0
export PATH="$HOME/.local/share/fnm/aliases/default/bin:$PATH"
if ! out=$(make -s check-fast 2>&1); then
  echo "make check-fast failed — fix before finishing:" >&2
  tail -n 40 <<<"$out" >&2
  exit 2
fi
exit 0
