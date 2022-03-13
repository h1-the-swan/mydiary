from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint
from .models import SpotifyTrack


class SpotifyTrackHistoryBase(SpotifyTrack):
    played_at: datetime


class SpotifyTrackHistory(SpotifyTrackHistoryBase, table=True):
    __table_args__ = (UniqueConstraint('spotify_id', 'played_at', name="uix_track_datetime"),)
    id: Optional[int] = Field(default=None, primary_key=True)


class SpotifyTrackHistoryCreate(SpotifyTrackHistoryBase):
    pass


class SpotifyTrackHistoryRead(SpotifyTrackHistoryBase):
    id: int
