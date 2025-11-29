import os
from collections import Counter
from typing import Dict, List, Tuple

from config import DIFF_DIR
from spotify_client import (
    find_or_create_playlist,
    get_playlist_tracks,
    incremental_update_playlist,
)
from models import Track, Classification
from cli_utils import print_progress_bar


def build_target_playlists(
    tracks: List[Track],
    classifications: Dict[str, Classification],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, List[str]]]:
    """
    For now: build a single global playlist "Auto – All" with all liked tracks.
    """
    playlists_mood: Dict[str, List[str]] = {}
    playlists_genre: Dict[str, List[str]] = {}
    playlists_year: Dict[str, List[str]] = {}

    playlist_name = "Auto – All"
    all_ids = [t.id for t in tracks if t.id]

    playlists_mood[playlist_name] = all_ids

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
) -> None:
    """
    Incremental sync with preview:
    - generate a .diff file per playlist WITH CHANGES in DIFF_DIR
    - remove existing duplicates
    - add only tracks that are not already present
    - do NOT remove tracks that are present but not in the target set
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
        print("No target playlists to sync.")
        return

    os.makedirs(DIFF_DIR, exist_ok=True)
    diffs = []

    print("\n=== Preview of incremental playlist changes ===")
    print("(Details are written to .diff files in the 'cache/diffs' folder')")

    total_playlists = len(target_playlists)
    # Show 0% before any work starts
    print_progress_bar(0, total_playlists, prefix="  Writing diff files")

    for idx, (name, target_ids) in enumerate(target_playlists.items(), start=1):
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

        # Update progress bar for this playlist
        print_progress_bar(idx, total_playlists, prefix="  Writing diff files")

        # If nothing changes for this playlist, no diff file, no detailed log
        if not duplicates and not new_to_add:
            print(f"\nPlaylist: {name}")
            print("  No changes for this playlist (already up to date).")
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

        # CLI output only for playlists with changes
        print(f"\nPlaylist: {name}")
        print(f"  Current        : {len(existing_ids)} tracks")
        print(f"  Target (unique): {len(target_set)} tracks")
        print(f"  Duplicates to remove : {len(duplicates)}")
        print(f"  New tracks to add    : {len(new_to_add)}")
        print(f"  → Details in: {diff_path}")

    # New line after progress bar
    print()

    # Check if ANY playlist actually needs changes
    has_changes = any(diff["duplicates"] or diff["new_to_add"] for diff in diffs)

    if not has_changes:
        print("\n✓ No changes detected. All playlists are already up to date.")
        print("No Spotify operations are required.")
        return

    # Global confirmation
    answer = (
        input("\nApply these incremental changes on Spotify? [Y/n] ").strip().lower()
    )
    if answer in ("n", "no"):
        print("→ Changes cancelled. No playlists were modified.")
        return

    print("\n→ Applying incremental changes...")
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

        print(f"  Incremental sync of playlist: {name}")
        incremental_update_playlist(token_info, playlist_id, target_ids)

    print("✓ Playlists synchronized (incremental).")
