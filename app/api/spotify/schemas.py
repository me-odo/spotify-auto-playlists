from typing import List

from pydantic import BaseModel


class PlaylistSummary(BaseModel):
    id: str
    name: str
    owner: str
    tracks_total: int
    is_owned: bool


PlaylistSummaryList = List[PlaylistSummary]
