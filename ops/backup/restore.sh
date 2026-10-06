#!/usr/bin/env bash
# Restore a backup into the running stack, replacing the current database.
#   ops/backup/restore.sh data/backups/kwak-20261006-030000.dump
set -euo pipefail
dump=${1:?usage: $0 <backup file>}
[[ -f "$dump" ]] || { echo "restore: no such file: $dump" >&2; exit 1; }

read -r -p "Replace the current database with $(basename "$dump")? Type 'restore': " answer
[[ "$answer" == restore ]] || { echo "restore: cancelled"; exit 1; }

docker compose stop api
# --clean --if-exists drops each object before recreating it from the dump.
docker compose exec -T db sh -c \
  'pg_restore --clean --if-exists --no-owner --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "$dump"
docker compose start api
echo "restore: done. Sign in again to check your data."
