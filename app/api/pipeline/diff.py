from typing import Dict, List

from fastapi import APIRouter, HTTPException

from app.core import Track, log_info, log_step
from app.pipeline import (
    apply_target_playlists,
    build_target_playlists,
    load_classification_cache,
    load_tracks_cache,
    preview_playlist_diffs,
)
from app.spotify import (
    SpotifyTokenMissing,
    build_spotify_auth_url,
    get_current_user_id,
    get_user_playlists,
    load_spotify_token,
)

from .schemas import (
    ApplyRequest,
    ApplyResponse,
    ApplyResult,
    DiffResponse,
    PlaylistDiff,
    TrackInfo,
)

router = APIRouter()


# --- Helpers ---------------------------------------------------------------


def _raise_unauth(e: SpotifyTokenMissing) -> None:
    raise HTTPException(
        status_code=401,
        detail={
            "status": "unauthenticated",
            "message": str(e) or "Spotify authorization required.",
            "auth_url": build_spotify_auth_url(),
        },
    )


def _track_to_info(track: Track) -> TrackInfo:
    return TrackInfo(
        id=track.id,
        name=track.name,
        artist=track.artist,
        album=track.album,
    )


# --- /pipeline/diff --------------------------------------------------------


@router.get("/diff", response_model=DiffResponse)
def get_diffs() -> DiffResponse:
    """
    Étape 5 : calcul des diffs entre l'état actuel des playlists Spotify
    et les playlists cibles générées à partir de la classification.

    - lit uniquement les caches (tracks + classification)
    - appelle Spotify en lecture (playlists existantes + contenus actuels)
    - NE MODIFIE RIEN sur Spotify
    """

    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing as e:
        _raise_unauth(e)

    # 1. Caches
    tracks = load_tracks_cache()
    if not tracks:
        raise HTTPException(
            status_code=400,
            detail="Tracks cache is empty. Run /pipeline/tracks first.",
        )

    classifications = load_classification_cache()
    if not classifications:
        raise HTTPException(
            status_code=400,
            detail="Classification cache is empty. Run /pipeline/classify first.",
        )

    # 2. Playlists existantes côté Spotify
    playlists_existing = get_user_playlists(token_info)

    # 3. Playlists cibles depuis la classification
    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    # 4. Diffs id-based
    log_step("Computing playlist diffs (preview)...")
    diffs_raw = preview_playlist_diffs(
        token_info=token_info,
        playlists_existing=playlists_existing,
        playlists_mood=playlists_mood,
        playlists_genre=playlists_genre,
        playlists_year=playlists_year,
    )

    # 5. Enrichir avec les métadonnées de tracks pour le front
    track_map: Dict[str, Track] = {t.id: t for t in tracks}

    playlists: List[PlaylistDiff] = []

    for d in diffs_raw:
        existing_ids = d["existing_ids"]
        target_ids = d["target_ids"]
        duplicates = d["duplicates"]
        new_to_add = d["new_to_add"]

        existing_tracks = [
            _track_to_info(track_map[tid]) for tid in existing_ids if tid in track_map
        ]
        target_tracks = [
            _track_to_info(track_map[tid]) for tid in target_ids if tid in track_map
        ]
        duplicates_tracks = [
            _track_to_info(track_map[tid]) for tid in duplicates if tid in track_map
        ]
        new_to_add_tracks = [
            _track_to_info(track_map[tid]) for tid in new_to_add if tid in track_map
        ]

        playlists.append(
            PlaylistDiff(
                name=d["name"],
                playlist_id=d.get("playlist_id"),
                existing_ids=existing_ids,
                target_ids=target_ids,
                duplicates=duplicates,
                new_to_add=new_to_add,
                existing_tracks=existing_tracks,
                target_tracks=target_tracks,
                duplicates_tracks=duplicates_tracks,
                new_to_add_tracks=new_to_add_tracks,
            )
        )

    log_info(f"Diff step: {len(playlists)} playlists analyzed.")

    return DiffResponse(
        status="done",
        playlists=playlists,
    )


# --- /pipeline/apply -------------------------------------------------------


@router.post("/apply", response_model=ApplyResponse)
def apply_playlists(payload: ApplyRequest) -> ApplyResponse:
    """
    Étape 6 : application des playlists cibles sur Spotify.

    Le frontend envoie la liste finale des playlists à appliquer :
    - name
    - playlist_id (optionnel, pour info)
    - target_ids (liste de track_ids finale, editable côté front)

    Cette route ne recalcule pas la classification ni les diffs :
    elle applique simplement le mapping explicite name -> target_ids.
    """

    if not payload.playlists:
        raise HTTPException(
            status_code=400,
            detail="No playlists provided in request payload.",
        )

    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing as e:
        _raise_unauth(e)

    # On a besoin de l'id user + des playlists existantes pour la création/sync
    user_id = get_current_user_id(token_info)
    playlists_existing = get_user_playlists(token_info)

    # Construire le mapping attendu par la couche pipeline
    target_playlists: Dict[str, List[str]] = {
        p.name: p.target_ids for p in payload.playlists
    }

    log_step(f"Applying {len(target_playlists)} playlists to Spotify...")
    results_raw = apply_target_playlists(
        token_info=token_info,
        user_id=user_id,
        playlists_existing=playlists_existing,
        target_playlists=target_playlists,
    )

    results = [
        ApplyResult(
            name=r["name"],
            playlist_id=r["playlist_id"],
            target_count=r["target_count"],
        )
        for r in results_raw
    ]

    return ApplyResponse(
        status="done",
        results=results,
    )
