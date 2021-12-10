import uuid
from typing import List, Dict, Union, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date
from pendulum import now
from pathlib import Path

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

# TODO
class GoogleCalendarEvent(BaseModel):
    id: str
    summary: str
    # what else? location? description? canceled/deleted?

class Tag(BaseModel):
    uid: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str

class MyDiaryImage(BaseModel):
    uid: uuid.UUID
    hash: bytes
    name: str
    filepath: Union[str, Path]
    description: str = None
    created_at: datetime = None

class MyDiaryDay(BaseModel):
    uid: uuid.UUID = Field(default_factory=uuid.uuid4)
    dt: date = now().date()
    tags: List[Tag] = []
    diary_txt: str = ""  # Markdown text
    joplin_note_id: str = None
    thumbnail: MyDiaryImage = None
    images: List[MyDiaryImage] = []
    spotify_songs: List[SpotifyTrack] = []  # Spotify songs played on this day
    pocket_articles: List[PocketArticle] = []  # interactions with Pocket articles on this day
    google_calendar_events: List[GoogleCalendarEvent] = []
    rating: Optional[int]  # (emotional) rating for the day. should it be an enum? should it also include a text description (and be its own object type)?
    flagged: bool = False  # flagged for inspection, in the case of some potential problem