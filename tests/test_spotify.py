import os, json
from pathlib import Path
from mydiary.models import SpotifyTrack
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def test_env_loaded():
    assert "SPOTIPY_CLIENT_ID" in os.environ
    assert "SPOTIPY_CLIENT_SECRET" in os.environ


def test_spotify_api_call():
    from mydiary.spotify_connector import MyDiarySpotify
    mydiary_spotify = MyDiarySpotify()
    assert isinstance(mydiary_spotify.sp, spotipy.Spotify)
    assert mydiary_spotify.sp.auth_manager is not None
    cached_token = mydiary_spotify.sp.auth_manager.cache_handler.get_cached_token()
    assert cached_token is not None
    r = mydiary_spotify.sp.current_user_recently_played()
    assert 'items' in r


def test_spotify_track(rootdir):
    fp = Path(rootdir).joinpath("spotifytrack.json")
    track_json = json.loads(fp.read_text())
    track = SpotifyTrack(
        id=track_json["track"]["id"],
        name=track_json["track"]["name"],
        artist_name=track_json["track"]["artists"][0]["name"],
        uri=track_json["track"]["uri"],
        played_at=track_json["played_at"],
    )
    assert track.name == "Always"
    assert track.artist_name == "Erasure"
    assert track.played_at.year == 2021
