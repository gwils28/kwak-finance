#!/usr/bin/env bash
# Prove a backup can be restored, without touching the real database (F-ADM-2):
# restore it into a throwaway Postgres and count what came back.
#   ops/backup/restore-test.sh                 # the newest backup in data/backups
#   ops/backup/restore-test.sh path/to/kwak-...dump
set -euo pipefail
dir=${KWAK_BACKUP_DIR:-data/backups}
dump=${1:-$(ls -1 "$dir"/kwak-*.dump 2>/dev/null | sort | tail -n 1)}
[[ -n "$dump" && -f "$dump" ]] || { echo "restore-test: no backup found in $dir" >&2; exit 1; }

name=kwak-restore-test-$$
docker run --rm -d --name "$name" -e POSTGRES_PASSWORD=test postgres:17-alpine >/dev/null
trap 'docker stop "$name" >/dev/null' EXIT
until docker exec "$name" pg_isready -U postgres -q; do sleep 0.5; done
sleep 1

docker exec -i "$name" pg_restore --no-owner --exit-on-error -U postgres -d postgres < "$dump"
docker exec "$name" psql -U postgres -tA -c \
  "SELECT 'accounts: ' || (SELECT count(*) FROM account)
     || ', transactions: ' || (SELECT count(*) FROM transaction)
     || ', last migration: ' || (SELECT version_num FROM alembic_version)"
echo "restore-test: OK, $(basename "$dump") restores cleanly"
