from fastapi import APIRouter, HTTPException

from app.core.logging_utils import log_info, log_step
from app.pipeline import enrich_tracks_with_external_features, load_tracks_cache

from .schemas import ExternalResponse

router = APIRouter()


@router.get("/external", response_model=ExternalResponse)
def get_external(force_refresh_missing_only: bool = True) -> ExternalResponse:
    """
    Étape 2 : enrichissement externe (MusicBrainz / AcousticBrainz).

    - Ne fait que des appels externes pour les morceaux manquants
      si force_refresh_missing_only=True (comportement par défaut).
    - Si force_refresh_missing_only=False, on force le recalcul complet.

    La gestion du cache est faite dans app.pipeline.external_features :
      - load_external_features_cache
      - save_external_features_cache
    """

    tracks = load_tracks_cache()
    if not tracks:
        raise HTTPException(
            status_code=400,
            detail="Tracks cache is empty. Run /pipeline/tracks first.",
        )

    log_step("External features step...")

    # NOTE : enrich_tracks_with_external_features s'occupe elle-même
    #        de charger / mettre à jour le cache.
    external_features, unmatched_tracks = enrich_tracks_with_external_features(
        tracks=tracks,
        force_refresh=not force_refresh_missing_only,
    )

    log_info(
        f"External features: {len(external_features)} entries, "
        f"{len(unmatched_tracks)} unmatched.",
    )

    return ExternalResponse(
        status="done",
        total_tracks=len(tracks),
        enriched=len(external_features),
        unmatched=len(unmatched_tracks),
    )
