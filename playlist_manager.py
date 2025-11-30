from collections import Counter
import os
from typing import Dict, List, Tuple, Callable

from config import DIFF_DIR, PLAYLIST_PREFIX_MOOD
from cli_utils import (
    print_header,
    print_step,
    print_info,
    print_success,
)
from fs_utils import ensure_dir
from models import Track, Classification
from spotify_client import (
    find_or_create_playlist,
    get_playlist_tracks,
    incremental_update_playlist,
)


def build_target_playlists(
    tracks: List[Track],
    classifications: Dict[str, Classification],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Build target playlists from track classifications.

    - playlists_mood:
        * "Auto – All" : all liked tracks
        * "Auto – Mood – X" : one playlist per mood (workout, chill, etc.),
          excluding "all" and "unclassified"

    - playlists_genre / playlists_year:
        currently empty (reserved for future use).
    """
    playlists_mood: Dict[str, List[str]] = {}
    playlists_genre: Dict[str, List[str]] = {}
    playlists_year: Dict[str, List[str]] = {}

    # 1) Global "All" playlist with all tracks
    all_ids = [t.id for t in tracks if t.id]
    playlists_mood["Auto – All"] = all_ids

    # 2) Mood-based playlists
    for t in tracks:
        if not t.id:
            continue
        c = classifications.get(t.id)
        if not c:
            continue

        mood = (c.mood or "unclassified").lower()
        if mood in ("all", "unclassified"):
            continue  # skip special buckets for now

        playlist_name = f"{PLAYLIST_PREFIX_MOOD}{mood.capitalize()}"

        if playlist_name not in playlists_mood:
            playlists_mood[playlist_name] = []

        # Avoid duplicates while preserving order
        if t.id not in playlists_mood[playlist_name]:
            playlists_mood[playlist_name].append(t.id)

    return playlists_mood, playlists_genre, playlists_year


def _find_playlist_by_name(playlists_existing: List[Dict], name: str):
    for p in playlists_existing:
        if p.get("name") == name:
            return p
    return None


def _safe_filename(name: str) -> str:
    """Transform a playlist name into a filesystem-safe filename."""
    cleaned = []
    for c in name:
        if c.isalnum():
            cleaned.append(c)
        elif c in (" ", "-", "_"):
            cleaned.append(c if c != " " else "_")
        else:
            cleaned.append("_")
    return "".join(cleaned)


def sync_playlists(
    token_info: Dict,
    user_id: str,
    playlists_existing: List[Dict],
    playlists_mood: Dict[str, List[str]],
    playlists_genre: Dict[str, List[str]],
    playlists_year: Dict[str, List[str]],
    track_map: Dict[str, Track],
    apply_changes: bool | None = None,
) -> list[Dict]:
    """
    Incremental sync with preview:
    - generate a .diff file per playlist WITH CHANGES in DIFF_DIR
    - remove existing duplicates
    - add only tracks that are not already present
    - do NOT remove tracks that are present but not in the target set

    apply_changes:
      - None  -> ask user in CLI (interactive)
      - True  -> apply changes without asking
      - False -> preview only, do NOT modify Spotify
    Returns:
      - list of diff dictionaries (one per target playlist)
    """
    # Merge all target playlists into a single dict
    target_playlists: Dict[str, List[str]] = {}
    for d in (playlists_mood, playlists_genre, playlists_year):
        for name, ids in d.items():
            target_playlists.setdefault(name, [])
            for tid in ids:
                if tid not in target_playlists[name]:
                    target_playlists[name].append(tid)

    if not target_playlists:
        print_info("No target playlists to sync.")
        return

    ensure_dir(DIFF_DIR)
    diffs = []

    print_header("Preview of incremental playlist changes")
    print_info("Details are written to .diff files in the 'cache/diffs' folder.")

    total_playlists = len(target_playlists)

    for idx, (name, target_ids) in enumerate(target_playlists.items(), start=1):
        print_info(f"[{idx}/{total_playlists}] Playlist: {name}")

        playlist_obj = _find_playlist_by_name(playlists_existing, name)
        if playlist_obj:
            playlist_id = playlist_obj["id"]
            existing_ids = get_playlist_tracks(token_info, playlist_id)
        else:
            playlist_id = None
            existing_ids = []

        counts = Counter(existing_ids)
        duplicates = [tid for tid, c in counts.items() if c > 1]

        existing_set = set(existing_ids)
        target_set = set(target_ids)

        new_to_add = list(target_set - existing_set)

        # Store diff info (used later to detect if ANY change exists)
        diffs.append(
            {
                "name": name,
                "playlist_id": playlist_id,
                "existing_ids": existing_ids,
                "target_ids": target_ids,
                "duplicates": duplicates,
                "new_to_add": new_to_add,
            }
        )

        # If nothing changes for this playlist, no diff file, minimal log
        if not duplicates and not new_to_add:
            print_info("  No changes for this playlist (already up to date).")
            continue

        # ----- Generate .diff file only if there are changes -----
        safe_name = _safe_filename(name)
        diff_path = os.path.join(DIFF_DIR, f"{safe_name}.diff")

        def fmt_track_line(prefix: str, tid: str) -> str:
            t = track_map.get(tid)
            if t:
                return f"{prefix} {t.artist} – {t.name} [{tid}]"
            return f"{prefix} {tid}"

        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(f"Playlist: {name}\n")
            f.write(f"Playlist ID: {playlist_id or '(will be created)'}\n\n")
            f.write(f"Current        : {len(existing_ids)} tracks\n")
            f.write(f"Target (unique): {len(target_set)} tracks\n")
            f.write(f"Duplicates to remove : {len(duplicates)}\n")
            f.write(f"New tracks to add    : {len(new_to_add)}\n")
            f.write("Tracks already present and not duplicated will be kept.\n\n")

            f.write("=== Duplicates to remove (d) ===\n")
            if duplicates:
                for tid in duplicates:
                    f.write(fmt_track_line("d", tid) + "\n")
            else:
                f.write("(no duplicates)\n")
            f.write("\n")

            f.write("=== New tracks to add (+) ===\n")
            if new_to_add:
                for tid in new_to_add:
                    f.write(fmt_track_line("+", tid) + "\n")
            else:
                f.write("(no new tracks to add)\n")

        print_info(f"  Current        : {len(existing_ids)} tracks")
        print_info(f"  Target (unique): {len(target_set)} tracks")
        print_info(f"  Duplicates to remove : {len(duplicates)}")
        print_info(f"  New tracks to add    : {len(new_to_add)}")
        print_step(f"Details in: {diff_path}")

    # ---- Summary & confirmation ----
    # Check if ANY playlist actually needs changes
    has_changes = any(diff["duplicates"] or diff["new_to_add"] for diff in diffs)

    if not has_changes:
        print_success("No changes detected. All playlists are already up to date.")
        print_info("No Spotify operations are required.")
        return diffs

    # Decide whether to apply changes
    if apply_changes is None:
        # CLI / interactive mode
        answer = (
            input("Apply these incremental changes on Spotify? [Y/n] ").strip().lower()
        )
        if answer in ("n", "no"):
            print_info("Changes cancelled. No playlists were modified.")
            return diffs
    elif apply_changes is False:
        # Non-interactive: preview only
        print_info("apply_changes=False → preview only. No playlists were modified.")
        return diffs
    # else: apply_changes is True → go ahead without asking

    print_step("Applying incremental changes on Spotify...")
    for diff in diffs:
        # Skip playlists that had no changes
        if not diff["duplicates"] and not diff["new_to_add"]:
            continue

        name = diff["name"]
        target_ids = diff["target_ids"]

        playlist_obj = _find_playlist_by_name(playlists_existing, name)
        if playlist_obj:
            playlist_id = playlist_obj["id"]
        else:
            playlist_id = find_or_create_playlist(
                token_info, user_id, name, playlists_existing
            )

        print_info(f"Incremental sync of playlist: {name}")
        incremental_update_playlist(token_info, playlist_id, target_ids)

    print_success("Playlists synchronized (incremental).")
    return diffs
