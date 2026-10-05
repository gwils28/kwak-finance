#!/usr/bin/env bash
# PostToolUse (Edit|Write): format the edited file with the project formatter.
set -uo pipefail
path=$(jq -r '.tool_input.file_path // empty')
[[ -f "$path" ]] || exit 0
root="$CLAUDE_PROJECT_DIR"
case "$path" in
  "$root"/backend/*.py)
    cd "$root/backend" && uv run -q ruff format -q "$path" && uv run -q ruff check -q --fix "$path" ;;
  "$root"/frontend/*.ts|"$root"/frontend/*.tsx|"$root"/frontend/*.css|"$root"/frontend/*.json)
    export PATH="$HOME/.local/share/fnm/aliases/default/bin:$PATH"
    cd "$root/frontend" && pnpm -s exec biome check --write "$path" >/dev/null ;;
esac
# Remaining lint errors are reported back to Claude without blocking the edit.
exit 0
