from pathlib import Path

from xianbot.database import resolve_sqlite_path


def test_resolve_sqlite_path_creates_parent(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "qxian.db"
    result = resolve_sqlite_path(f"sqlite:///{target.as_posix()}")
    assert result == target
    assert target.parent.exists()
