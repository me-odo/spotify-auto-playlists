import json
import os
import tempfile
from typing import Any, Callable, Optional


def ensure_parent_dir(path: str) -> None:
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


def write_json(path: str, data: Any) -> None:
    """
    Write a JSON file in a robust, atomic way.

    Steps:
    1. Ensure the parent directory exists.
    2. Write the JSON content to a temporary file in the same directory.
    3. Flush and fsync the file descriptor.
    4. Atomically replace the target file with the temporary file.

    This guarantees that:
    - there is never a partially written file at `path`,
    - the function only returns once the data has been durably written.
    """
    ensure_parent_dir(path)

    directory = os.path.dirname(path) or "."
    tmp_file = None

    try:
        # Create a temporary file in the same directory as the target.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            delete=False,
        ) as tmp:
            tmp_file = tmp.name
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())

        # Atomic rename: on POSIX systems, this is guaranteed to be atomic.
        os.replace(tmp_file, path)

    finally:
        # In case of an exception before os.replace, try to clean up.
        if (
            tmp_file is not None
            and os.path.exists(tmp_file)
            and os.path.basename(tmp_file) != os.path.basename(path)
        ):
            try:
                os.remove(tmp_file)
            except OSError:
                # Best-effort cleanup, ignore failures.
                pass


def read_json(
    path: str,
    default: Any = None,
    *,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> Any:
    """
    Read a JSON file.
    - returns `default` if the file does not exist
    - returns `default` if JSON is invalid (optionally calling on_error)
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
