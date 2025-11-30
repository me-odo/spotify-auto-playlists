import os
import json
from typing import Any, Callable, Optional


def ensure_parent_dir(path: str) -> None:
    """
    Ensure the parent directory of a given file path exists.
    Example:
      ensure_parent_dir("/tmp/my/cache/file.json")
    """
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


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
    Write a JSON file, ensuring the parent directory exists.
    """
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
