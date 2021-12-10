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


# def test_spotify_api_call():
#     scopes = ["user-library-read", "user-read-recently-played", "user-top-read"]
#     sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scopes))
#     r = sp.current_user_recently_played()
#     assert 'items' in r


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
