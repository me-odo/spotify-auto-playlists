import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Optional


def ensure_parent_dir(path: Path | str) -> None:
    """
    Ensure the parent directory of a given file path exists.
    Example:
      ensure_parent_dir("/tmp/my/cache/file.json")
    """
    ensure_dir(os.path.dirname(path))


def ensure_dir(directory: str) -> None:
    """
    Ensure a directory exists. If it doesn't, create it.
    Example:
      ensure_dir("/tmp/my/cache")
    """
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def write_json(path: str | Path, data: Any) -> None:
    """
    Write JSON data to a file using an atomic replace.

    The JSON content is first written to a temporary file in the same directory
    as the target path. The temporary file is flushed and fsynced to ensure
    the data is safely persisted on disk, then atomically moved over the
    target path using os.replace.

    This makes the operation robust against partial writes or process crashes:
    callers will either see the previous valid file contents or the new full
    JSON document, but never a truncated or corrupted file.
    """
    target_path = Path(path)
    ensure_parent_dir(target_path)

    # Create a temporary file in the same directory as the target file.
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=target_path.name,
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Atomically replace the target file with the temporary file.
        os.replace(tmp_path, target_path)
    except Exception:
        # Best-effort cleanup of the temporary file if something goes wrong.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_json(
    path: str,
    default: Any = None,
    *,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> Any:
    """
    Read a JSON file safely.

    - returns `default` if the file does not exist
    - returns `default` if JSON is invalid or corrupted (optionally calling on_error)

    This makes it safe to call against cache/job files that may be partially
    written or corrupted on disk; callers can rely on either a fully parsed
    object or the provided `default` value.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        if on_error:
            on_error(e)
        return default
