#!/usr/bin/env bash
# Commit the given paths, open a PR, wait for GitHub to allow the merge, squash-merge it,
# then return to an up-to-date main. Run by the maintainer, from a topic branch.
#
#   scripts/ship-pr.sh "feat(api): add rules" "Why this change." backend/ frontend/src
#
# It never bypasses anything: no --admin, no --no-verify. It stops when a check fails, when
# the branch is behind main or conflicts, or after 30 minutes.
set -euo pipefail

usage() { echo "usage: $0 <subject> <body|\"\"> <path>..." >&2; exit 2; }
[[ $# -ge 3 ]] || usage
subject=$1 body=$2
shift 2

branch=$(git branch --show-current)
if [[ -z "$branch" || "$branch" == main ]]; then
  echo "ship-pr: run it from a topic branch, not '${branch:-detached HEAD}'." >&2
  exit 1
fi

git add -- "$@"
if git diff --cached --quiet; then
  echo "ship-pr: nothing staged in: $*" >&2
  exit 1
fi
if [[ -n "$body" ]]; then
  git commit -m "$subject" -m "$body"
else
  git commit -m "$subject"
fi
git push -u origin HEAD
gh pr create --title "$subject" --body "${body:-$subject}"

# Wait on GitHub's own verdict (mergeStateStatus) rather than on the checks visible so far:
# a job that starts late (docker waits for backend and frontend) is still counted.
deadline=$((SECONDS + 1800))
while :; do
  pr=$(gh pr view --json mergeStateStatus,statusCheckRollup)
  failed=$(jq -r '.statusCheckRollup[]
    | select((.conclusion // .state // "") | test("FAILURE|ERROR|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE"))
    | .name // .context' <<<"$pr")
  if [[ -n "$failed" ]]; then
    echo "ship-pr: check failed, not merging: $(tr '\n' ' ' <<<"$failed")" >&2
    gh pr checks || true
    exit 1
  fi
  case $(jq -r .mergeStateStatus <<<"$pr") in
    CLEAN) break ;;
    BEHIND)
      echo "ship-pr: the branch is behind main. Click 'Update with rebase' on the PR, then: gh pr merge --squash --delete-branch" >&2
      exit 1 ;;
    DIRTY)
      echo "ship-pr: the branch conflicts with main: resolve it, push, then: gh pr merge --squash --delete-branch" >&2
      exit 1 ;;
  esac
  if ((SECONDS > deadline)); then
    echo "ship-pr: still not mergeable after 30 minutes, see: gh pr checks" >&2
    exit 1
  fi
  sleep 10
done

gh pr merge --squash --delete-branch
git switch main
git pull --ff-only
