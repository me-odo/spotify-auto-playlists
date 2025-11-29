import os


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
