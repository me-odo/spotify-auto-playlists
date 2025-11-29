import sys
import time


def print_progress_bar(
    current: int, total: int, prefix: str = "", length: int = 30
) -> None:
    """
    Simple textual progress bar.
    Example:
    [##########----------] 33.3%
    """
    if total <= 0:
        sys.stdout.write(f"\r{prefix} ...")
        sys.stdout.flush()
        return

    ratio = current / total
    percent = ratio * 100
    filled_len = int(length * ratio)
    bar = "#" * filled_len + "-" * (length - filled_len)
    sys.stdout.write(f"\r{prefix} [{bar}] {percent:5.1f}%")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()


def spinner(message: str, duration: float = 0.1):
    """
    Very simple spinner generator. Use in loops:

        spin = spinner("Working")
        next(spin)  # update
    """
    symbols = ["|", "/", "-", "\\"]
    index = 0
    while True:
        sys.stdout.write(f"\r{message} {symbols[index]}")
        sys.stdout.flush()
        time.sleep(duration)
        index = (index + 1) % len(symbols)
        yield
