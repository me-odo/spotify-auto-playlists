"""Rule-based track classification using external features.

This module assigns a coarse-grained classification (mood/genre/year) to each
Spotify track based on external_features produced by
app.pipeline.external_features.enrich_tracks_with_external_features.

The core function, classify_tracks_rule_based(), is intentionally simple and
deterministic so that it can be called both from the CLI pipeline and from
API-driven workflows.

Important constraint:
  - This module must remain side-effect free except for updating and persisting
    the classification cache on disk. It must not perform any Spotify I/O or
    other external side effects.
"""

from typing import Dict, List

from app.core.logging_utils import log_info
from app.core.models import Classification, Track
from app.pipeline.cache_manager import (
    load_classification_cache,
    save_classification_cache,
)


def classify_tracks_rule_based(
    tracks: List[Track],
    external_features: Dict[str, dict],
    refresh_existing: bool = False,
) -> Dict[str, Classification]:
    """
    Classification rule-based des morceaux.

    Entrées
    -------
    tracks : List[Track]
        Liste de tous les morceaux likés (depuis le cache tracks).
    external_features : Dict[str, dict]
        Dictionnaire {track_id -> features externes} construit par
        app.pipeline.external_features.enrich_tracks_with_external_features.
    refresh_existing : bool
        - False (défaut) : on NE recalculera que les morceaux non encore
          présents dans le cache de classification.
        - True : on recalcule TOUT, même ceux déjà classés.

    Comportement
    ------------
    - Charge le cache de classification existant (si présent)
    - Parcourt la liste des tracks
    - Pour chaque track :
        * si refresh_existing=False et track déjà dans le cache → skip
        * sinon, on déduit mood/genre/year à partir de external_features
    - Sauvegarde le cache complet sur disque
    - Retourne un mapping {track_id -> Classification}
    """

    # 1. Chargement du cache existant
    cache: Dict[str, Classification] = load_classification_cache()

    # 2. Parcours de tous les morceaux
    for track in tracks:
        track_id = track.id
        if not track_id:
            # Track mal formé, on l'ignore
            continue

        # On saute les morceaux déjà classés sauf si on force la mise à jour
        if not refresh_existing and track_id in cache:
            continue

        features = external_features.get(track_id)
        if not features:
            # Aucune feature externe → on marque ce morceau comme "non classé"
            cache[track_id] = Classification(mood="unclassified")
            continue

        # ⚠ TODO : remplace cette logique par ta vraie règle métier.
        # Ici on fait une version ultra simplifiée qui suppose que tu as déjà
        # mappé 'mood', 'genre' et 'year' dans external_features.
        mood = (features.get("mood") or "unclassified").lower()
        genre = features.get("genre")
        year = features.get("year")

        cache[track_id] = Classification(
            mood=mood,
            genre=genre,
            year=year,
        )

    # 3. Sauvegarde du cache complet
    save_classification_cache(cache)

    log_info(f"Classification cache saved for {len(cache)} tracks.")
    return cache
