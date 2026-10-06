# Operations

## Backups (F-ADM-1)

The `backup` service of `docker-compose.yml` dumps the whole database with `pg_dump` (custom
format) every day at `KWAK_BACKUP_TIME` (default `03:00`, in `TZ`, default `Europe/Paris`),
and once at start-up when the newest backup is more than a day old. Each dump is checked with
`pg_restore --list` before it gets its final name, so a half-written file never looks like a
backup.

Files land in `KWAK_BACKUP_DIR` on the host (default `data/backups/`, git-ignored) as
`kwak-YYYYMMDD-HHMMSS.dump`. Retention keeps the newest backup of each of the last 7 days,
4 weeks and 12 months; older dumps are deleted. Other files in the directory are left alone.

First time:

```bash
mkdir -p data/backups      # before `make up`, or Docker creates it owned by root
make up
docker compose logs backup # "backup: kwak-....dump (... bytes)"
```

Optional settings in `.env`: `KWAK_BACKUP_DIR`, `KWAK_BACKUP_TIME`, `TZ`, and `KWAK_UID` /
`KWAK_GID` when your user id is not 1000 (`id -u`, `id -g`).

**Keep a copy elsewhere.** A backup on the same disk does not survive the disk. Copy
`data/backups/` to an external drive or a NAS from time to time (open question Q7), and keep
`KWAK_SECRET_KEY` with it: without the key, TOTP has to be set up again after a restore. The
dumps hold your financial data unencrypted: store them like the originals.

## Test a backup (F-ADM-2)

```bash
ops/backup/restore-test.sh                 # the newest backup in data/backups
ops/backup/restore-test.sh path/to/kwak-20261006-030000.dump
```

It restores the dump into a throwaway Postgres container, prints how many accounts and
transactions came back and the schema version, then removes the container. The real database
is never touched. Run it after the first backup, then every month or so.

## Restore

```bash
ops/backup/restore.sh data/backups/kwak-20261006-030000.dump
```

It asks for confirmation, stops the API, replaces the database with the dump and restarts the
API. Everything recorded after that backup is lost: re-import the statements since then (the
import skips what is already there). If the dump comes from an older version of the app, run
`docker compose exec api kwak migrate` afterwards.
