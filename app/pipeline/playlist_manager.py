"""Playlist target construction and synchronization helpers.

This module is responsible for building target playlists from tracks and their
classifications (mood/genre/year) and then synchronizing those targets with
Spotify.

It exposes:
  - CLI-style helpers such as sync_playlists(), which generate .diff files
    on disk and optionally apply incremental changes.
  - API-oriented helpers preview_playlist_diffs() and apply_target_playlists(),
    which are designed to be called from the HTTP layer.

The API-oriented functions must remain side-effect free except for the actual
Spotify operations they trigger (no filesystem writes, no hidden mutations),
so that they can be safely used in request/response workflows.
"""

from collections import Counter
import os
from typing import Any, Dict, List, Tuple

from app.config import DIFF_DIR, PLAYLIST_PREFIX_MOOD
from app.core import (
    Classification,
    Track,
    ensure_dir,
    log_info,
    log_section,
    log_step,
    log_success,
)
from app.spotify import (
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


def _merge_target_playlists(
    playlists_mood: Dict[str, List[str]],
    playlists_genre: Dict[str, List[str]],
    playlists_year: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """
    Merge mood/genre/year target playlists into a single mapping.

    The merge preserves the order of track IDs and avoids duplicates
    within each playlist.
    """
    target_playlists: Dict[str, List[str]] = {}
    for source in (playlists_mood, playlists_genre, playlists_year):
        for name, ids in source.items():
            bucket = target_playlists.setdefault(name, [])
            for tid in ids:
                if tid not in bucket:
                    bucket.append(tid)
    return target_playlists


def _compute_playlist_diff(
    name: str,
    target_ids: List[str],
    playlists_existing: List[Dict],
    token_info: Dict,
) -> Dict[str, Any]:
    """
    Compute the diff information for a single playlist name.

    Returns a dict compatible with the structure documented in sync_playlists().
    """
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

    return {
        "name": name,
        "playlist_id": playlist_id,
        "existing_ids": existing_ids,
        "target_ids": target_ids,
        "duplicates": duplicates,
        "new_to_add": new_to_add,
    }


def _format_track_line(track_map: Dict[str, Track], prefix: str, tid: str) -> str:
    """
    Human-readable representation of a track line in a diff file.
    """
    track = track_map.get(tid)
    if track:
        return f"{prefix} {track.artist} – {track.name} [{tid}]"
    return f"{prefix} {tid}"


def _write_diff_file(
    diff_entry: Dict[str, Any],
    track_map: Dict[str, Track],
) -> str:
    """
    Write the .diff file for a single playlist and return the file path.
    """
    name = diff_entry["name"]
    playlist_id = diff_entry["playlist_id"]
    existing_ids = diff_entry["existing_ids"]
    target_ids = diff_entry["target_ids"]
    duplicates = diff_entry["duplicates"]
    new_to_add = diff_entry["new_to_add"]

    safe_name = _safe_filename(name)
    diff_path = os.path.join(DIFF_DIR, f"{safe_name}.diff")

    target_set = set(target_ids)

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
                f.write(_format_track_line(track_map, "d", tid) + "\n")
        else:
            f.write("(no duplicates)\n")
        f.write("\n")

        f.write("=== New tracks to add (+) ===\n")
        if new_to_add:
            for tid in new_to_add:
                f.write(_format_track_line(track_map, "+", tid) + "\n")
        else:
            f.write("(no new tracks to add)\n")

    return diff_path


def _should_apply_changes(apply_changes: bool) -> bool:
    """
    Decide whether playlist changes should be applied to Spotify.

    Returns True if the operation should proceed, False if it should be a preview only.
    """
    if not apply_changes:
        log_info("Preview mode: no changes will be applied to Spotify.")
        return False
    return True


def sync_playlists(
    token_info: Dict,
    user_id: str,
    playlists_existing: List[Dict],
    playlists_mood: Dict[str, List[str]],
    playlists_genre: Dict[str, List[str]],
    playlists_year: Dict[str, List[str]],
    track_map: Dict[str, Track],
    apply_changes: bool = False,
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
    # 1) Merge all target sources into a single dict
    target_playlists = _merge_target_playlists(
        playlists_mood=playlists_mood,
        playlists_genre=playlists_genre,
        playlists_year=playlists_year,
    )

    if not target_playlists:
        log_info("No target playlists to sync.")
        return []

    ensure_dir(DIFF_DIR)
    diffs: List[Dict[str, Any]] = []

    log_section("Preview of incremental playlist changes")
    log_info(
        "Diff details will be written to .diff files in the 'cache/diffs' folder.\n"
    )

    total_playlists = len(target_playlists)

    # 2) Build diff entries and write .diff files when there are changes
    for idx, (name, target_ids) in enumerate(target_playlists.items(), start=1):
        log_info(f"[{idx}/{total_playlists}] Playlist: {name}")

        diff_entry = _compute_playlist_diff(
            name=name,
            target_ids=target_ids,
            playlists_existing=playlists_existing,
            token_info=token_info,
        )
        diffs.append(diff_entry)

        duplicates = diff_entry["duplicates"]
        new_to_add = diff_entry["new_to_add"]

        # If nothing changes for this playlist, no diff file, minimal log
        if not duplicates and not new_to_add:
            log_info("  No changes for this playlist (already up to date).")
            continue

        diff_path = _write_diff_file(diff_entry, track_map)

        existing_ids = diff_entry["existing_ids"]
        target_set = set(diff_entry["target_ids"])

        log_info(f"  Current        : {len(existing_ids)} tracks")
        log_info(f"  Target (unique): {len(target_set)} tracks")
        log_info(f"  Duplicates to remove : {len(duplicates)}")
        log_info(f"  New tracks to add    : {len(new_to_add)}")
        log_step(f"Diff written to: {diff_path}\n")

    # 3) Check if ANY playlist actually needs changes
    has_changes = any(d["duplicates"] or d["new_to_add"] for d in diffs)

    if not has_changes:
        log_success("No changes detected. All playlists are already up to date.")
        log_info("No Spotify operations are required.")
        return diffs

    # 4) Decide whether to apply changes (preview or actual update)
    if not _should_apply_changes(apply_changes):
        return diffs

    # 5) Either apply_changes is True, or user confirmed
    log_step("Applying incremental changes to Spotify...")

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
            diff["playlist_id"] = playlist_id  # keep info in sync with reality

        log_info(f"  Incremental sync of playlist: {name}")
        incremental_update_playlist(token_info, playlist_id, target_ids)

    log_success("Playlists synchronized (incremental).")
    return diffs


# ---------------------------------------------------------------------------
# New helpers for API-based diff visualisation / apply
# ---------------------------------------------------------------------------


def preview_playlist_diffs(
    token_info: Dict,
    playlists_existing: List[Dict],
    playlists_mood: Dict[str, List[str]],
    playlists_genre: Dict[str, List[str]],
    playlists_year: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """
    Compute diffs for all target playlists WITHOUT:
      - writing .diff files
      - applying any change on Spotify

    This is intended for API usage (frontend diff visualisation).
    """
    target_playlists = _merge_target_playlists(
        playlists_mood=playlists_mood,
        playlists_genre=playlists_genre,
        playlists_year=playlists_year,
    )

    if not target_playlists:
        return []

    diffs: List[Dict[str, Any]] = []
    for name, target_ids in target_playlists.items():
        diff_entry = _compute_playlist_diff(
            name=name,
            target_ids=target_ids,
            playlists_existing=playlists_existing,
            token_info=token_info,
        )
        diffs.append(diff_entry)

    return diffs


def apply_target_playlists(
    token_info: Dict,
    user_id: str,
    playlists_existing: List[Dict],
    target_playlists: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """
    Apply a final, explicit mapping name -> target_ids to Spotify.

    This is the function used by the /pipeline/apply endpoint, where the
    frontend has already decided the final target content of each playlist.

    It does NOT recompute diffs; it just ensures a playlist exists and then
    calls incremental_update_playlist with the provided target_ids.
    """
    results: List[Dict[str, Any]] = []

    for name, target_ids in target_playlists.items():
        playlist_obj = _find_playlist_by_name(playlists_existing, name)
        if playlist_obj:
            playlist_id = playlist_obj["id"]
        else:
            playlist_id = find_or_create_playlist(
                token_info,
                user_id,
                name,
                playlists_existing,
            )
            # Important: keep local list in sync if we reuse it later
            playlists_existing.append({"id": playlist_id, "name": name})

        log_info(f"Applying target playlist for '{name}' ({len(target_ids)} tracks)...")
        incremental_update_playlist(token_info, playlist_id, target_ids)

        results.append(
            {
                "name": name,
                "playlist_id": playlist_id,
                "target_count": len(target_ids),
            }
        )

    log_success(f"Applied {len(results)} target playlists to Spotify.")
    return results
