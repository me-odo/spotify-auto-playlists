import sys


def print_header(title: str) -> None:
    """Top-level section header."""
    print(f"\n=== {title} ===")


def print_info(message: str) -> None:
    """Neutral information (no icon, just slight indent)."""
    print(f"{message}")


def print_step(message: str) -> None:
    """Action step / ongoing work."""
    print(f"→ {message}")


def print_success(message: str) -> None:
    """Successful outcome."""
    print(f"✅ {message}")


def print_warning(message: str) -> None:
    """Warning / non-fatal problem."""
    print(f"⚠️  {message}")


def print_error(message: str) -> None:
    """Error / fatal problem."""
    print(f"❌ {message}")


def print_question(message: str) -> None:
    """Prompt for user input."""
    # Just a visual convention; you still call input() yourself
    print(f"?  {message}", end="")


def print_progress_bar(
    current: int,
    total: int,
    prefix: str = "",
    length: int = 30,
) -> None:
    """
    Simple progress bar in the terminal.

    - In CLI mode: uses a single-line bar with carriage return (\r).
    - In GUI mode: prints a simple "current/total (xx.x%)" line,
      because carriage returns do not work nicely in a Text widget.
    """
    if total <= 0:
        total = 1

    fraction = max(0.0, min(1.0, current / total))
    percent = fraction * 100

    # If we're in GUI mode (stdout replaced by our TextRedirector), we avoid \r
    if getattr(sys.stdout, "is_gui", False):
        line = f"{prefix} {current}/{total} ({percent:5.1f}%)\n"
        sys.stdout.write(line)
        sys.stdout.flush()
        return

    # Classic CLI progress bar with carriage return
    filled_length = int(length * fraction)
    bar = "#" * filled_length + "-" * (length - filled_length)
    line = f"\r{prefix} [{bar}] {percent:5.1f}%"
    sys.stdout.write(line)
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()
