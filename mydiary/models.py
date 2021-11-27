from pydantic import BaseModel
from datetime import datetime

# TODO
class SpotifyTrack(BaseModel):
    id: str
    name: str
    artist_name: str
    uri: str
    played_at: datetime = None

# TODO
class PocketArticle(BaseModel):
    id: str
    given_title: str
    resolved_title: str
    url: str