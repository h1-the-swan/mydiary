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

import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler, SpotifyOauthError
from spotipy import SpotifyException
from sqlmodel import SQLModel

from .models import (
    SpotifyTrack,
    SpotifyTrackHistory,
    SpotifyTrackHistoryFrozen,
    SpotifyContextTypeEnum,
    SpotifyTrackAudioFeatures,
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


class SpotifyTrackNotFound(Exception):
    """Spotify says there is no track with this ID (or the ID isn't a track ID)"""


class SpotifyUnavailable(Exception):
    """Spotify couldn't be asked: network error, auth failure, rate limit, 5xx"""


# errors meaning Spotify couldn't be asked, besides SpotifyException. EOFError is
# spotipy prompting on stdin for a token it can't refresh.
UNAVAILABLE_ERRORS = (SpotifyOauthError, requests.exceptions.RequestException, EOFError)


class TrackSummary(SQLModel):
    # what the PerformSong form shows for one Spotify track
    spotify_id: str
    name: str
    artist_name: str  # every artist, joined with ", " like SpotifyTrackBase.parse_track
    album_name: Optional[str] = None
    release_year: Optional[int] = None
    thumbnail_url: Optional[str] = None

    @classmethod
    def from_track(cls, t: Dict) -> "TrackSummary":
        album = t.get("album") or {}
        # release_date is "YYYY", "YYYY-MM" or "YYYY-MM-DD"; some tracks have "0000"
        year = (album.get("release_date") or "")[:4]
        release_year = int(year) if year.isdigit() and int(year) > 0 else None
        # the smallest album image is the one a list row needs
        images = album.get("images") or []
        thumbnail_url = None
        if images:
            smallest = min(images, key=lambda img: img.get("width") or float("inf"))
            thumbnail_url = smallest.get("url")
        return cls(
            spotify_id=t["id"],
            name=t["name"],
            artist_name=", ".join(artist["name"] for artist in t["artists"]),
            album_name=album.get("name"),
            release_year=release_year,
            thumbnail_url=thumbnail_url,
        )


class MyDiarySpotify:
    def __init__(self, sp: Optional[spotipy.Spotify] = None) -> None:
        self.sp = sp
        if self.sp is None:
            self.sp = spotipy.Spotify()
        if self.sp.auth_manager is None:
            self.sp.auth_manager = SpotifyOAuth(
                scope=scopes,
                open_browser=False,
                requests_timeout=5,
                cache_handler=CacheFileHandler(
                    cache_path=os.environ.get("SPOTIFY_TOKEN_CACHE_PATH", None)
                ),
            )

        self.context_cache = {}

    def get_track(self, spotify_id: str) -> Dict:
        """Fetch one track's data from Spotify, by ID, URI or open.spotify.com URL.

        Raises SpotifyTrackNotFound or SpotifyUnavailable.
        """
        try:
            track_id = normalize_spotify_id(spotify_id.strip())
        except ValueError as e:
            raise SpotifyTrackNotFound(str(e)) from e
        if not track_id:
            raise SpotifyTrackNotFound("empty spotify id")
        self._check_token()
        try:
            t = self.sp.track(track_id)
        except SpotifyException as e:
            # 400 is a malformed ID, 404 a well-formed one with no track
            if e.http_status in (400, 404):
                raise SpotifyTrackNotFound(track_id) from e
            raise SpotifyUnavailable(str(e)) from e
        except UNAVAILABLE_ERRORS as e:
            raise SpotifyUnavailable(str(e)) from e
        if not t:
            # spotipy returns None for a 200 whose body isn't JSON
            raise SpotifyUnavailable(f"empty response for track {track_id}")
        return t

    def _check_token(self) -> None:
        # with no cached token, spotipy falls back to prompting on stdin, which
        # in the backend container raises EOFError (and prints a prompt to the
        # logs). Treat a missing token as Spotify being unavailable instead.
        cache_handler = getattr(self.sp.auth_manager, "cache_handler", None)
        if cache_handler is not None and cache_handler.get_cached_token() is None:
            raise SpotifyUnavailable("no cached Spotify token")

    def lookup_track(self, spotify_id: str) -> TrackSummary:
        return TrackSummary.from_track(self.get_track(spotify_id))

    def search_tracks(self, q: str, limit: int = 10) -> List[TrackSummary]:
        """Search Spotify's catalog for tracks. Raises SpotifyUnavailable."""
        q = q.strip()
        if not q:
            return []
        self._check_token()
        try:
            r = self.sp.search(q, limit=limit, type="track")
        except (SpotifyException,) + UNAVAILABLE_ERRORS as e:
            raise SpotifyUnavailable(str(e)) from e
        if not r:
            raise SpotifyUnavailable(f"empty response for search {q!r}")
        # items can contain nulls for tracks Spotify has pulled
        return [
            TrackSummary.from_track(t) for t in r["tracks"]["items"] if t is not None
        ]

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    def add_or_update_track_in_database(
        self,
        track: Union[Dict, SpotifyTrack],
        session: Optional[Session] = None,
        commit: bool = True,
    ) -> SpotifyTrack:
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
            ret = spotify_track
        else:
            # db_track = db_track.update_track_data(track_data)
            db_track.name = spotify_track.name
            db_track.artist_name = spotify_track.artist_name
            db_track.uri = spotify_track.uri
            # session.add(db_track)
            ret = db_track

        if commit is True:
            session.commit()

        return ret

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

    def add_or_update_audio_features_in_database(
        self,
        spotify_id: str,
        session: Session,
        commit: bool = True,
    ) -> None:
        db_track = session.get(SpotifyTrack, spotify_id)
        db_track.audio_features = SpotifyTrackAudioFeatures.from_api_response(
            self.sp.audio_features(spotify_id)
        )
        db_track.audio_features.updated_at = pendulum.now().in_timezone("UTC")
        session.add(db_track)
        if commit is True:
            session.commit()

    def save_one_track_but_not_history(
        self,
        t: Union[Dict, SpotifyTrackHistory],
        session: Session,
        commit: bool = True,
        add_or_update_audio_features: bool = False,
    ):
        db_track = self.add_or_update_track_in_database(
            t, session=session, commit=False
        )
        session.add(db_track)
        if add_or_update_audio_features is True:
            spotify_id = db_track.spotify_id
            self.add_or_update_audio_features_in_database(
                spotify_id, session=session, commit=False
            )
        if commit is True:
            session.commit()
        return "added_track_but_not_history"

    def save_one_track_to_database(
        self,
        t: Union[Dict, SpotifyTrackHistory],
        session: Session,
        commit: bool = True,
        add_or_update_track: bool = True,
        add_or_update_audio_features: bool = False,
    ) -> str:
        if isinstance(t, SpotifyTrackHistory):
            spotify_track_history = t
        else:
            spotify_track_history: SpotifyTrackHistory = (
                SpotifyTrackHistory.from_spotify_track(t)
            )
        spotify_id = spotify_track_history.spotify_id
        if spotify_track_history.played_at is None:
            if add_or_update_track is True:
                return self.save_one_track_but_not_history(
                    t,
                    session=session,
                    commit=commit,
                    add_or_update_audio_features=add_or_update_audio_features,
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
        if add_or_update_audio_features is True:
            try:
                self.add_or_update_audio_features_in_database(
                    spotify_id, session=session, commit=False
                )
            except (SpotifyException, AttributeError) as e:
                logger.error(f"FAILURE when trying to get spotify audio features: {e}")
        if commit is True:
            session.commit()
        return "added"

    def save_recent_tracks_to_database(
        self,
        session: Optional[Session] = None,
        add_or_update_audio_features: bool = False,
    ) -> int:
        logger.info(
            "getting recently played Spotify tracks from API and saving to database"
        )
        if session is None:
            session = self.new_session()
        recent_tracks: List[Dict] = self.sp.current_user_recently_played()["items"]
        num_added = 0
        num_skipped = 0
        for t in recent_tracks:
            r = self.save_one_track_to_database(
                t,
                session,
                commit=False,
                add_or_update_audio_features=add_or_update_audio_features,
            )
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
