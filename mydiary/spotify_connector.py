# -*- coding: utf-8 -*-

DESCRIPTION = """Get spotify data using the Spotify API and the spotipy library"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
from timeit import default_timer as timer
from typing import Dict, Optional, List

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

scopes = ["user-library-read", "user-read-recently-played", "user-top-read"]

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


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

    def get_tracks_for_day(self, items: List[Dict], dt: datetime) -> List[SpotifyTrack]:
        """get the spotify tracks for a given day from an input list, and convert them to SpotifyTrack objects

        Args:
            items (List[Dict]): list of spotify tracks from the Spotify API
            dt (datetime): date to match

        """
        # Note that the Spotify API only returns the last 50 played songs. So this won't work well for historical dates, or if you played a lot of songs per day.
        tracks = []
        for t in items:
            dt_track = pendulum.parse(t["played_at"])
            if dt_track.in_timezone(dt.timezone).date() == dt.date():
                tracks.append(SpotifyTrack.from_spotify_track(t))
        return tracks
