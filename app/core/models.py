from dataclasses import dataclass
from typing import Dict, Optional


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
