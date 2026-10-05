#!/usr/bin/env bash
# PreToolUse (Read|Edit|Write): protect real financial data and secrets.
set -euo pipefail
input=$(cat)
tool=$(jq -r '.tool_name' <<<"$input")
path=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ -z "$path" ]] && exit 0
rel=${path#"$CLAUDE_PROJECT_DIR"/}

case "$rel" in
  .env|.env.*|*.pem|*.key)
    [[ "$rel" == ".env.example" ]] && exit 0
    echo "Blocked: $rel holds secrets." >&2; exit 2 ;;
esac

if [[ "$tool" != "Read" && "$rel" == data/* ]]; then
  echo "Blocked: data/ holds real financial data and is read-only for Claude." >&2; exit 2
fi
exit 0
