#!/usr/bin/env bash
# PreToolUse (Edit|Write): a migration merged into main is frozen, databases already ran it.
set -euo pipefail
path=$(jq -r '.tool_input.file_path // empty')
rel=${path#"$CLAUDE_PROJECT_DIR"/}
[[ "$rel" == backend/packages/api/src/kwak_api/migrations/versions/*.py ]] || exit 0
cd "$CLAUDE_PROJECT_DIR"
base=$(git rev-parse -q --verify origin/main || git rev-parse -q --verify main) || exit 0
if git cat-file -e "$base:$rel" 2>/dev/null; then
  echo "Blocked: $rel is merged into main. Write a new migration instead (skill db-migration)." >&2
  exit 2
fi
exit 0
