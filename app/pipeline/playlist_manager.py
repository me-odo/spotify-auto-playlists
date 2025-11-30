from collections import Counter
import os
from typing import Dict, List, Tuple, Any, Optional

from app.config import DIFF_DIR, PLAYLIST_PREFIX_MOOD
from app.core.cli_utils import (
    print_header,
    print_step,
    print_info,
    print_success,
)
from app.core.fs_utils import ensure_dir
from app.core.models import Track, Classification
from app.spotify.playlists import (
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
    apply_changes: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Incrementally sync target playlists to Spotify, with a diff preview.

    Behaviour:
      - Merge all target playlists (mood/genre/year) into a single name -> track_ids map.
      - For each target playlist:
          * detect duplicates currently in Spotify
          * compute which new tracks would be added
          * generate a .diff file ONLY if something changes (duplicates or additions)
      - Show a summary per playlist in the CLI.

    apply_changes:
      - None  => interactive (CLI): ask the user for confirmation.
      - False => PREVIEW-ONLY: generate diffs, do NOT touch Spotify.
      - True  => apply changes directly on Spotify, without confirmation.

    Returns:
      - A list of diff dicts, one per target playlist, of the form:
        {
          "name": str,
          "playlist_id": Optional[str],
          "existing_ids": List[str],
          "target_ids": List[str],
          "duplicates": List[str],
          "new_to_add": List[str],
        }
    """
    # Merge all target sources into a single dict
    target_playlists: Dict[str, List[str]] = {}
    for d in (playlists_mood, playlists_genre, playlists_year):
        for name, ids in d.items():
            target_playlists.setdefault(name, [])
            for tid in ids:
                if tid not in target_playlists[name]:
                    target_playlists[name].append(tid)

    if not target_playlists:
        print_info("No target playlists to sync.")
        return []

    ensure_dir(DIFF_DIR)
    diffs: List[Dict[str, Any]] = []

    print_header("Preview of incremental playlist changes")
    print_info(
        "Diff details will be written to .diff files in the 'cache/diffs' folder.\n"
    )

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
        diff_entry: Dict[str, Any] = {
            "name": name,
            "playlist_id": playlist_id,
            "existing_ids": existing_ids,
            "target_ids": target_ids,
            "duplicates": duplicates,
            "new_to_add": new_to_add,
        }
        diffs.append(diff_entry)

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
        print_step(f"Diff written to: {diff_path}\n")

    # Check if ANY playlist actually needs changes
    has_changes = any(d["duplicates"] or d["new_to_add"] for d in diffs)

    if not has_changes:
        print_success("No changes detected. All playlists are already up to date.")
        print_info("No Spotify operations are required.")
        return diffs

    # If apply_changes is False => preview only, do not touch Spotify
    if apply_changes is False:
        print_info("Preview mode: no changes will be applied to Spotify.")
        return diffs

    # If apply_changes is None => interactive CLI: ask user
    if apply_changes is None:
        answer = (
            input("Apply these incremental changes on Spotify? [Y/n] ").strip().lower()
        )
        if answer in ("n", "no"):
            print_info("Changes cancelled. No playlists were modified.")
            return diffs

    # Either apply_changes is True, or user confirmed
    print_step("Applying incremental changes to Spotify...")

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
            diff["playlist_id"] = playlist_id  # mettre à jour l'info dans le diff

        print_info(f"  Incremental sync of playlist: {name}")
        incremental_update_playlist(token_info, playlist_id, target_ids)

    print_success("Playlists synchronized (incremental).")
    return diffs
