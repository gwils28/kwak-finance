#!/usr/bin/env python3
"""Daily pg_dump with rotation (F-ADM-1). Runs in the postgres image: stdlib only.

    python3 backup.py          # loop: back up at KWAK_BACKUP_TIME (default 03:00) every day
    python3 backup.py --now    # one backup, then prune

Environment: KWAK_DATABASE_URL, KWAK_BACKUP_DIR (default /backups), KWAK_BACKUP_TIME, TZ.
Retention: the newest backup of each of the last 7 days, 4 weeks and 12 months.
"""

# Naive local times on purpose: file names and the schedule follow the container's TZ, so
# "03:00" is 3 a.m. at home. pg_dump/pg_restore come from the image, with fixed arguments.
# ruff: noqa: DTZ005, DTZ007, S603, S607

import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from pathlib import Path

NAME = re.compile(r"^kwak-(\d{8}-\d{6})\.dump$")
STAMP = "%Y%m%d-%H%M%S"
KEEP_DAYS, KEEP_WEEKS, KEEP_MONTHS = 7, 4, 12


def backup_name(when: datetime) -> str:
    return f"kwak-{when.strftime(STAMP)}.dump"


def parse_name(name: str) -> datetime | None:
    match = NAME.match(name)
    return datetime.strptime(match.group(1), STAMP) if match else None


def _newest_per_bucket(
    moments: list[datetime], bucket: Callable[[datetime], object], count: int
) -> set[datetime]:
    """The newest moment of each of the `count` most recent buckets."""
    kept: dict[object, datetime] = {}
    for moment in sorted(moments, reverse=True):
        key = bucket(moment)
        if key not in kept:
            if len(kept) == count:
                break
            kept[key] = moment
    return set(kept.values())


def to_keep(names: Iterable[str]) -> set[str]:
    """Backup file names to keep; other names (not backups) are ignored."""
    by_moment = {m: n for n in names if (m := parse_name(n)) is not None}
    moments = list(by_moment)
    keep = (
        _newest_per_bucket(moments, lambda m: m.date(), KEEP_DAYS)
        | _newest_per_bucket(moments, lambda m: m.isocalendar()[:2], KEEP_WEEKS)
        | _newest_per_bucket(moments, lambda m: (m.year, m.month), KEEP_MONTHS)
    )
    return {by_moment[m] for m in keep}


def to_prune(names: Iterable[str]) -> list[str]:
    names = list(names)
    keep = to_keep(names)
    return sorted(n for n in names if parse_name(n) is not None and n not in keep)


def libpq_url(url: str) -> str:
    """The app's SQLAlchemy URL ("postgresql+psycopg://...") as pg_dump expects it."""
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


def back_up(directory: Path, url: str) -> Path:
    """Dump, check the dump reads back, then publish it under its final name."""
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / backup_name(datetime.now())
    partial = final.with_suffix(".partial")
    subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", f"--file={partial}", libpq_url(url)],
        check=True,
    )
    subprocess.run(["pg_restore", "--list", str(partial)], check=True, stdout=subprocess.DEVNULL)
    partial.replace(final)
    for name in to_prune(p.name for p in directory.iterdir()):
        (directory / name).unlink()
    print(f"backup: {final.name} ({final.stat().st_size} bytes)", flush=True)
    return final


def _latest(directory: Path) -> datetime | None:
    moments = [m for p in directory.glob("kwak-*.dump") if (m := parse_name(p.name))]
    return max(moments, default=None)


def due_on_start(latest: datetime | None, now: datetime) -> bool:
    """Back up right away when starting if the last backup is missing or over a day old."""
    return latest is None or now - latest > timedelta(hours=24)


def seconds_until(hour: int, minute: int, now: datetime) -> float:
    """Until the next hour:minute, today or tomorrow."""
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main() -> None:
    url = os.environ["KWAK_DATABASE_URL"]
    directory = Path(os.environ.get("KWAK_BACKUP_DIR", "/backups"))
    if "--now" in sys.argv:
        back_up(directory, url)
        return
    hour, minute = (int(x) for x in os.environ.get("KWAK_BACKUP_TIME", "03:00").split(":"))
    directory.mkdir(parents=True, exist_ok=True)
    if due_on_start(_latest(directory), datetime.now()):
        back_up(directory, url)
    while True:
        time.sleep(seconds_until(hour, minute, datetime.now()))
        try:
            back_up(directory, url)
        except subprocess.CalledProcessError as exc:  # keep the service alive for tomorrow
            print(f"backup failed: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
