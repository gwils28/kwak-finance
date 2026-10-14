#!/usr/bin/env bash
# Stop: remind Claude to update the in-app guides (CLAUDE.md rules) when the branch changes
# what users see or how the app is run, but the matching guide is untouched.
# It nags once per new set of files, so "nothing user-visible changed" is an acceptable answer.
set -uo pipefail
input=$(cat)
[[ "$(jq -r '.stop_hook_active' <<<"$input")" == "true" ]] && exit 0
cd "$CLAUDE_PROJECT_DIR"

base=$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD)
changed=$( { git diff --name-only "$base"; git ls-files --others --exclude-standard; } | sort -u)

visible=$(grep -E '^frontend/src/.*\.(tsx|ts|css)$' <<<"$changed" \
  | grep -vE '\.test\.tsx?$|^frontend/src/(api/generated|test|guide|runGuide)/|^frontend/src/(test-setup\.ts|i18n/(guide|runGuide|index)\.tsx?)$')
ops=$(grep -E '^(docker-compose\.yml|Makefile|\.env\.example|backend/Dockerfile|frontend/(Dockerfile|Caddyfile)|ops/.*|backend/packages/api/src/kwak_api/(cli|migrate|settings)\.py)$' <<<"$changed")

msg=""
if [[ -n "$visible" ]] && ! grep -qx 'frontend/src/i18n/guide.ts' <<<"$changed"; then
  msg+="The UI changed but frontend/src/i18n/guide.ts did not (guide page and 'Getting started' checklist, EN and FR):"$'\n'"$visible"$'\n'
fi
if [[ -n "$ops" ]] && ! grep -qx 'frontend/src/i18n/runGuide.ts' <<<"$changed"; then
  msg+="How the app is run changed but frontend/src/i18n/runGuide.ts did not (EN and FR):"$'\n'"$ops"$'\n'
fi
[[ -z "$msg" ]] && exit 0

marker="${TMPDIR:-/tmp}/kwak-stop-guides-$(jq -r '.session_id' <<<"$input")"
sum=$(md5sum <<<"$msg")
[[ -f "$marker" && "$(cat "$marker")" == "$sum" ]] && exit 0
echo "$sum" >"$marker"
printf '%sUpdate the guide in this PR, or say why nothing users see or run changed.\n' "$msg" >&2
exit 2
