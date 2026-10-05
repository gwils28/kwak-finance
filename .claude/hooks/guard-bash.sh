#!/usr/bin/env bash
# PreToolUse (Bash): sole-contributor policy and no git hook bypass.
# Only git invocations are inspected, so docs that mention these words can still be edited.
set -euo pipefail
cmd=$(jq -r '.tool_input.command // empty')
grep -qE '(^|[;&|(]|\s)git\s' <<<"$cmd" || exit 0
if grep -qiE 'git\s.*(co-authored-by|--no-verify)|git\s+config\s.*core\.hooksPath' <<<"$cmd"; then
  echo "Blocked: co-author trailers, --no-verify and hooksPath changes are not allowed. The maintainer commits." >&2
  exit 2
fi
exit 0
