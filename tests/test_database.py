import sqlite3
from pathlib import Path

from xianbot.config import get_settings
from xianbot.database import initialize_database, resolve_sqlite_path


def test_resolve_sqlite_path_creates_parent(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "qxian.db"
    result = resolve_sqlite_path(f"sqlite:///{target.as_posix()}")
    assert result == target
    assert target.parent.exists()


def test_initialize_database_applies_sqlite_pragmas(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "pragma" / "qxian.db"
    monkeypatch.setenv("QXIAN_DATABASE_URL", f"sqlite:///{target.as_posix()}")
    monkeypatch.setenv("QXIAN_SQLITE_JOURNAL_MODE", "WAL")
    monkeypatch.setenv("QXIAN_SQLITE_SYNCHRONOUS", "NORMAL")
    monkeypatch.setenv("QXIAN_SQLITE_BUSY_TIMEOUT_MS", "12000")
    monkeypatch.setenv("QXIAN_SQLITE_CACHE_SIZE_KB", "4096")
    monkeypatch.setenv("QXIAN_SQLITE_MMAP_SIZE_MB", "32")
    monkeypatch.setenv("QXIAN_SQLITE_WAL_AUTOCHECKPOINT", "400")
    monkeypatch.setenv("QXIAN_SQLITE_JOURNAL_SIZE_LIMIT_MB", "16")
    monkeypatch.setenv("QXIAN_SQLITE_TEMP_STORE", "MEMORY")
    get_settings.cache_clear()

    db_path = initialize_database(get_settings().database_url)

    with sqlite3.connect(db_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout = 12000")
        connection.execute("PRAGMA cache_size = -4096")
        connection.execute("PRAGMA mmap_size = 33554432")
        connection.execute("PRAGMA wal_autocheckpoint = 400")
        connection.execute("PRAGMA journal_size_limit = 16777216")
        connection.execute("PRAGMA temp_store = MEMORY")
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        cache_size = connection.execute("PRAGMA cache_size").fetchone()[0]
        mmap_size = connection.execute("PRAGMA mmap_size").fetchone()[0]
        wal_autocheckpoint = connection.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
        journal_size_limit = connection.execute("PRAGMA journal_size_limit").fetchone()[0]
        temp_store = connection.execute("PRAGMA temp_store").fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    assert int(synchronous) == 1
    assert int(busy_timeout) == 12000
    assert int(cache_size) == -4096
    assert int(mmap_size) >= 32 * 1024 * 1024
    assert int(wal_autocheckpoint) == 400
    assert int(journal_size_limit) == 16 * 1024 * 1024
    assert int(temp_store) == 2
    get_settings.cache_clear()
