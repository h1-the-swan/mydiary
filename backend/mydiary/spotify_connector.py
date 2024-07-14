# -*- coding: utf-8 -*-

DESCRIPTION = """Get spotify data using the Spotify API and the spotipy library"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import re
from urllib.parse import urlsplit
import pendulum
from timeit import default_timer as timer
from typing import Dict, Optional, List, Union

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

from .models import (
    SpotifyTrack,
    SpotifyTrackHistory,
    SpotifyTrackHistoryFrozen,
    SpotifyContextTypeEnum,
)
from .db import engine, Session, select

scopes = ["user-library-read", "user-read-recently-played", "user-top-read"]


def normalize_spotify_id(s: str) -> str:
    if re.match(r"https?:\/\/", s):
        if "spotify" not in s:
            raise ValueError(f"This doesn't seem to be a valid spotify id: {s}")
        p = urlsplit(s).path
        return p.split("/")[-1]
    elif ":" in s:
        if "spotify" not in s:
            raise ValueError(f"This doesn't seem to be a valid spotify id: {s}")
        return s.split(":")[-1]
    else:
        return s


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

        self.context_cache = {}

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    def add_or_update_track_in_database(
        self,
        track: Union[Dict, SpotifyTrack],
        session: Optional[Session] = None,
        commit: bool = True,
    ) -> None:
        if session is None:
            session = self.new_session()
        if isinstance(track, SpotifyTrack):
            spotify_id = track.spotify_id
            spotify_track = track
        else:
            if "track" in track:
                track_data = track["track"]
            else:
                track_data = track
            spotify_id = track_data["id"]
            spotify_track = SpotifyTrack.from_spotify_track(track)
        db_track = session.get(SpotifyTrack, spotify_id)
        if db_track is None:
            session.add(spotify_track)
        else:
            # db_track = db_track.update_track_data(track_data)
            db_track.name = spotify_track.name
            db_track.artist_name = spotify_track.artist_name
            db_track.uri = spotify_track.uri
            # session.add(db_track)

        if commit is True:
            session.commit()

    def check_existing_history(
        self, spotify_id: str, played_at: datetime, session: Session
    ) -> Union[SpotifyTrackHistory, None]:
        stmt = (
            select(SpotifyTrackHistory)
            .where(SpotifyTrackHistory.spotify_id == spotify_id)
            .where(SpotifyTrackHistory.played_at == played_at)
        )
        existing_row = session.exec(stmt).one_or_none()
        return existing_row

    def save_one_track_to_database(
        self,
        t: Union[Dict, SpotifyTrackHistory],
        session: Session,
        commit: bool = True,
        add_or_update_track: bool = True,
    ) -> SpotifyTrackHistory:
        if isinstance(t, SpotifyTrackHistory):
            spotify_track_history = t
        else:
            spotify_track_history: SpotifyTrackHistory = (
                SpotifyTrackHistory.from_spotify_track(t)
            )
        existing_row = self.check_existing_history(
            spotify_id=spotify_track_history.spotify_id,
            played_at=spotify_track_history.played_at,
            session=session,
        )
        if existing_row:
            return "skipped"
        if spotify_track_history.context_uri is not None:
            context = self.hydrate_context(spotify_track_history.context_uri)
            spotify_track_history.context_name = context["context_name"]
            spotify_track_history.context_type = context["context_type"]
        session.add(spotify_track_history)
        if add_or_update_track is True:
            self.add_or_update_track_in_database(t, session=session, commit=False)
        if commit is True:
            session.commit()
        return "added"

    def save_recent_tracks_to_database(self, session: Optional[Session] = None) -> int:
        logger.info(
            "getting recently played Spotify tracks from API and saving to database"
        )
        if session is None:
            session = self.new_session()
        recent_tracks: List[Dict] = self.sp.current_user_recently_played()["items"]
        num_added = 0
        num_skipped = 0
        for t in recent_tracks:
            r = self.save_one_track_to_database(t, session, commit=False)
            if r == "skipped":
                num_skipped += 1
            elif r == "added":
                num_added += 1
        logger.debug(
            f"skipped {num_skipped} tracks because they were already in the database"
        )
        logger.info(f"adding {num_added} new rows (in spotifytrackhistory) to database")
        session.commit()
        return num_added

    def get_tracks_for_day(
        self, dt: datetime, session: Optional[Session] = None
    ) -> List[SpotifyTrackHistoryFrozen]:
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
        r = session.exec(stmt).all()
        return [
            SpotifyTrackHistoryFrozen(
                id=t.id,
                played_at=t.played_at,
                track=t.track,
                context_name=t.context_name,
                context_type=t.context_type,
                context_uri=t.context_uri,
            )
            for t in r
        ]

    def hydrate_context(self, context_uri: str, force: bool = False) -> Dict:
        if context_uri in self.context_cache and force is False:
            return self.context_cache[context_uri]
        bypass_cache = False
        try:
            if "playlist" in context_uri:
                r = self.sp.playlist(context_uri, fields="id,uri,name,type")
                context_uri = r["uri"]
                context_name = r["name"]
                context_type = r["type"]
            elif "artist" in context_uri:
                r = self.sp.artist(context_uri)
                context_uri = r["uri"]
                context_name = r["name"]
                context_type = r["type"]
            elif "album" in context_uri:
                r = self.sp.album(context_uri)
                artists = ", ".join([artist["name"] for artist in r["artists"]])
                album_name = f"{artists} - {r['name']}"
                context_uri = r["uri"]
                context_name = album_name
                context_type = r["type"]
            else:
                raise ValueError(
                    "invalid context_uri. must be one of [playlist, album, artist]"
                )
        except spotipy.SpotifyException as e:
            logger.warning(f"HTTPError found when trying to get data for {context_uri}")
            logger.exception(e)
            context_name = ""
            context_type = context_uri.split(":")[1]
        context = {
            "context_uri": context_uri,
            "context_name": context_name,
            "context_type": SpotifyContextTypeEnum[context_type].value,
        }
        if bypass_cache is False:
            self.context_cache[context_uri] = context
        return context
