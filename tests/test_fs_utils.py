from pathlib import Path

from app.core import ensure_dir, ensure_parent_dir, read_json, write_json


def test_read_json_missing_file_returns_default(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    default = {"value": 123}

    result = read_json(str(path), default=default)

    assert result == default


def test_read_json_invalid_json_calls_on_error_and_returns_default(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{ invalid json", encoding="utf-8")

    errors = []

    def on_error(exc: Exception) -> None:
        errors.append(exc)

    default = {"ok": True}

    result = read_json(str(path), default=default, on_error=on_error)

    assert result == default
    assert len(errors) == 1


def test_write_json_creates_parent_dirs_and_roundtrips(tmp_path: Path) -> None:
    data = {"foo": "bar", "nested": {"a": 1}, "list": [1, 2]}
    path = tmp_path / "nested" / "path" / "data.json"

    write_json(path, data)

    assert path.exists()
    loaded = read_json(str(path), default=None)
    assert loaded == data


def test_ensure_dir_and_ensure_parent_dir(tmp_path: Path) -> None:
    dir_path = tmp_path / "some" / "dir"
    ensure_dir(str(dir_path))

    assert dir_path.exists()
    assert dir_path.is_dir()

    file_path = tmp_path / "parent" / "sub" / "file.json"
    ensure_parent_dir(file_path)

    assert file_path.parent.exists()
    assert file_path.parent.is_dir()
