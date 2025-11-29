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


def build_target_playlists(
    tracks: List[Track],
    classifications: Dict[str, Classification],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, List[str]]]:
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


from collections import Counter


def _find_playlist_by_name(playlists_existing: List[Dict], name: str):
    for p in playlists_existing:
        if p.get("name") == name:
            return p
    return None


def _find_playlist_by_name(playlists_existing: List[Dict], name: str):
    for p in playlists_existing:
        if p.get("name") == name:
            return p
    return None


def _safe_filename(name: str) -> str:
    # Transforme un nom de playlist en nom de fichier safe
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
    Version avec prévisualisation incrémentale :
    - génère un fichier .diff par playlist dans DIFF_DIR
    - supprime les doublons existants
    - ajoute uniquement les titres absents
    - ne supprime PAS les titres qui ne sont pas dans la cible
    """
    # Fusionner toutes les playlists cibles dans un seul dict
    target_playlists: Dict[str, List[str]] = {}
    for d in (playlists_mood, playlists_genre, playlists_year):
        for name, ids in d.items():
            target_playlists.setdefault(name, [])
            for tid in ids:
                if tid not in target_playlists[name]:
                    target_playlists[name].append(tid)

    if not target_playlists:
        print("Aucune playlist cible à synchroniser.")
        return

    os.makedirs(DIFF_DIR, exist_ok=True)
    diffs = []

    print("\n=== Prévisualisation des modifications de playlists (incrémental) ===")
    print(
        "(Les détails sont écrits dans des fichiers .diff dans le dossier 'cache/diffs')"
    )

    for name, target_ids in target_playlists.items():
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

        # ----- Génération du .diff -----
        safe_name = _safe_filename(name)
        diff_path = os.path.join(DIFF_DIR, f"{safe_name}.diff")

        def fmt_track_line(prefix: str, tid: str) -> str:
            t = track_map.get(tid)
            if t:
                return f"{prefix} {t.artist} – {t.name} [{tid}]"
            return f"{prefix} {tid}"

        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(f"Playlist: {name}\n")
            f.write(f"Playlist ID: {playlist_id or '(sera créée)'}\n\n")
            f.write(f"Actuel        : {len(existing_ids)} titres\n")
            f.write(f"Cible (unique): {len(target_set)} titres\n")
            f.write(f"Doublons à supprimer : {len(duplicates)}\n")
            f.write(f"Nouvels titres à ajouter : {len(new_to_add)}\n")
            f.write("Les titres déjà présents et non dupliqués resteront.\n\n")

            f.write("=== Doublons à supprimer (d) ===\n")
            if duplicates:
                for tid in duplicates:
                    f.write(fmt_track_line("d", tid) + "\n")
            else:
                f.write("(aucun doublon)\n")
            f.write("\n")

            f.write("=== Nouveaux titres à ajouter (+) ===\n")
            if new_to_add:
                for tid in new_to_add:
                    f.write(fmt_track_line("+", tid) + "\n")
            else:
                f.write("(aucun nouvel ajout)\n")

        print(f"\nPlaylist: {name}")
        print(f"  Actuel        : {len(existing_ids)} titres")
        print(f"  Cible (unique): {len(target_set)} titres")
        print(f"  Doublons à supprimer : {len(duplicates)}")
        print(f"  Nouveaux titres à ajouter : {len(new_to_add)}")
        print(f"  → Détails dans : {diff_path}")

    # Confirmation globale
    answer = (
        input("\nAppliquer ces modifications incrémentales sur Spotify ? [Y/n] ")
        .strip()
        .lower()
    )
    if answer in ("n", "no", "non"):
        print("→ Modifications annulées. Aucune playlist n'a été modifiée.")
        return

    print("\n→ Application des modifications incrémentales…")
    for diff in diffs:
        name = diff["name"]
        target_ids = diff["target_ids"]

        playlist_obj = _find_playlist_by_name(playlists_existing, name)
        if playlist_obj:
            playlist_id = playlist_obj["id"]
        else:
            playlist_id = find_or_create_playlist(
                token_info, user_id, name, playlists_existing
            )

        print(f"  Sync incrémentale de la playlist: {name}")
        incremental_update_playlist(token_info, playlist_id, target_ids)

    print("✓ Playlists synchronisées (incrémental).")
