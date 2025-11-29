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
    mood: str
    genre_macro: str
    extra: Dict
