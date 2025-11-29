import os
from typing import List
from config import REPORTS_DIR
from models import Track


def _ensure_dir(directory: str) -> None:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def write_unmatched_report(unmatched_tracks: List[Track], filename: str) -> str:
    """
    Write a markdown report listing all tracks for which we couldn't find
    external mood/genre features.
    Returns the full path of the report file.
    """
    # Make sure the reports directory exists
    _ensure_dir(REPORTS_DIR)

    path = os.path.join(REPORTS_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Tracks without external mood/genre features\n\n")
        f.write(f"Total unmatched: {len(unmatched_tracks)}\n\n")

        unmatched_sorted = sorted(
            unmatched_tracks,
            key=lambda t: (t.artist or "", t.name or ""),
        )

        current_artist = None
        for t in unmatched_sorted:
            if t.artist != current_artist:
                if current_artist is not None:
                    f.write("\n")
                current_artist = t.artist
                f.write(f"## {current_artist or 'Unknown artist'}\n")
            f.write(f"- {t.name or 'Unknown title'} (spotify:track:{t.id})\n")

    return path
