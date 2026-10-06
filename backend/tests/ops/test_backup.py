"""ops/backup/backup.py runs in the Postgres image (stdlib only); its logic is tested here."""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

from hypothesis import given
from hypothesis import strategies as st


def _load() -> ModuleType:
    path = Path(__file__).parents[3] / "ops" / "backup" / "backup.py"
    spec = importlib.util.spec_from_file_location("kwak_backup", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backup = _load()
T0 = datetime(2026, 10, 6, 3, 0)  # noqa: DTZ001 (backup names use the container's local time)


def _name(when: datetime) -> str:
    name: str = backup.backup_name(when)
    return name


def test_backup_names_sort_by_time() -> None:
    assert _name(T0) == "kwak-20261006-030000.dump"
    assert backup.parse_name("kwak-20261006-030000.dump") == T0
    assert backup.parse_name("notes.txt") is None


def test_a_year_of_daily_backups_keeps_7_days_4_weeks_and_12_months() -> None:
    names = [_name(T0 - timedelta(days=d)) for d in range(365)]
    kept = backup.to_keep(names)
    days = sorted((backup.parse_name(n) for n in kept), reverse=True)
    assert days[:7] == [T0 - timedelta(days=d) for d in range(7)]
    assert len(kept) <= 7 + 4 + 12
    assert len(kept) >= 12


def test_the_newest_backup_of_a_day_wins() -> None:
    morning, evening = T0.replace(hour=1), T0.replace(hour=23)
    kept = backup.to_keep([_name(morning), _name(evening)])
    assert _name(evening) in kept
    assert _name(morning) not in kept


def test_files_that_are_not_backups_are_never_pruned() -> None:
    assert backup.to_prune(["README.txt", _name(T0)]) == []


times = st.lists(
    st.integers(min_value=0, max_value=800 * 24).map(lambda h: T0 - timedelta(hours=h)),
    unique=True,
    max_size=60,
)


@given(times)
def test_the_newest_backup_is_always_kept(moments: list[datetime]) -> None:
    names = [_name(m) for m in moments]
    kept = backup.to_keep(names)
    assert kept <= set(names)
    if names:
        assert _name(max(moments)) in kept
    assert sorted(set(names) - kept) == sorted(backup.to_prune(names))


@given(times)
def test_pruning_twice_removes_nothing_more(moments: list[datetime]) -> None:
    kept = backup.to_keep([_name(m) for m in moments])
    assert backup.to_keep(sorted(kept)) == kept


def test_pg_dump_gets_a_libpq_url() -> None:
    url = "postgresql+psycopg://kwak:secret@db:5432/kwak"
    assert backup.libpq_url(url) == "postgresql://kwak:secret@db:5432/kwak"


def test_a_backup_runs_on_start_only_when_the_last_is_over_a_day_old() -> None:
    assert backup.due_on_start(None, T0)
    assert not backup.due_on_start(T0 - timedelta(hours=23), T0)
    assert backup.due_on_start(T0 - timedelta(hours=25), T0)


def test_the_next_run_is_today_or_tomorrow_at_the_set_time() -> None:
    assert backup.seconds_until(3, 0, T0.replace(hour=2)) == 3600
    assert backup.seconds_until(3, 0, T0) == 24 * 3600
