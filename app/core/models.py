from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


@dataclass
class Track:
    id: str
    name: str
    artist: str
    album: str
    release_date: Optional[str]
    added_at: Optional[str]
    features: Dict


@dataclass
class Classification:
    """
    Résultat de la classification d’un morceau.

    - mood  : "chill", "workout", etc.
    - genre : éventuellement un genre macro (facultatif)
    - year  : année dominante (facultatif)
    """

    mood: str
    genre: Optional[str] = None
    year: Optional[int] = None


class TrackEnrichment(BaseModel):
    """
    Unified enrichment entry for a track.

    - source     : logical source of the enrichment (e.g. "external_features")
    - version    : optional version string for the enrichment pipeline
    - timestamp  : when the enrichment was computed (UTC naive or tz-aware)
    - categories : free-form mapping of enrichment keys to values
    """

    source: str
    version: Optional[str] = None
    timestamp: datetime
    categories: Dict[str, Any]
