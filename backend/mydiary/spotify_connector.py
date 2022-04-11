# -*- coding: utf-8 -*-

DESCRIPTION = """Get spotify data using the Spotify API and the spotipy library"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
from timeit import default_timer as timer
from typing import Dict, Optional, List

from sqlalchemy import desc

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler

from .models import SpotifyTrack
from .spotify_history import (
    SpotifyTrackHistory,
    SpotifyTrackHistoryCreate,
    SpotifyTrackHistoryRead,
)
from .db import engine, Session, select

scopes = ["user-library-read", "user-read-recently-played", "user-top-read"]

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


class MyDiarySpotify:
    def __init__(self, sp: Optional[spotipy.Spotify] = None) -> None:
        self.sp = sp
        if self.sp is None:
            self.sp = spotipy.Spotify()
        if self.sp.auth_manager is None:
            self.sp.auth_manager = SpotifyOAuth(
                scope=scopes,
                open_browser=False,
                cache_handler=CacheFileHandler(
                    cache_path=os.environ.get("SPOTIFY_TOKEN_CACHE_PATH", None)
                ),
            )

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    def save_recent_tracks_to_database(self, session: Optional[Session] = None):
        logger.info(
            "getting recently played Spotify tracks from API and saving to database"
        )
        if session is None:
            session = self.new_session()
        recent_tracks = self.sp.current_user_recently_played()["items"]
        num_added = 0
        num_skipped = 0
        for t in recent_tracks:
            spotify_track = SpotifyTrackHistoryCreate.from_spotify_track(t)
            stmt = (
                select(SpotifyTrackHistory)
                .where(SpotifyTrackHistory.spotify_id == spotify_track.spotify_id)
                .where(SpotifyTrackHistory.played_at == spotify_track.played_at)
            )
            existing_row = session.exec(stmt).one_or_none()
            if existing_row:
                num_skipped += 1
                continue
            session.add(SpotifyTrackHistory.from_orm(spotify_track))
            num_added += 1
        logger.debug(
            f"skipped {num_skipped} tracks because they were already in the database"
        )
        logger.info(f"adding {num_added} new rows to database")
        session.commit()

    def get_tracks_for_day(
        self, dt: datetime, session: Optional[Session] = None
    ) -> List[SpotifyTrack]:
        """get the spotify tracks for a given day from the database

        Args:
            dt (datetime): date to match

        """
        if session is None:
            session = self.new_session()
        dt = pendulum.instance(dt)
        start = dt.start_of("day").in_timezone("UTC")
        end = dt.end_of("day").in_timezone("UTC")
        stmt = (
            select(SpotifyTrackHistory)
            .where(SpotifyTrackHistory.played_at >= start)
            .where(SpotifyTrackHistory.played_at <= end)
            .order_by(desc(SpotifyTrackHistory.played_at))
        )
        return session.exec(stmt).all()
