import os, json
import pytest
from pathlib import Path
import pendulum
from mydiary.models import SpotifyTrack, SpotifyTrackHistory
from mydiary.spotify_connector import normalize_spotify_id
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


def test_env_loaded():
    assert "SPOTIPY_CLIENT_ID" in os.environ
    assert "SPOTIPY_CLIENT_SECRET" in os.environ


@pytest.mark.external_api
def test_spotify_api_call():
    from mydiary.spotify_connector import MyDiarySpotify

    mydiary_spotify = MyDiarySpotify()
    assert isinstance(mydiary_spotify.sp, spotipy.Spotify)
    assert mydiary_spotify.sp.auth_manager is not None
    cached_token = mydiary_spotify.sp.auth_manager.cache_handler.get_cached_token()
    assert cached_token is not None
    r = mydiary_spotify.sp.current_user_recently_played()
    assert "items" in r


@pytest.mark.parametrize("input_id,expected", [
    ("4oGTdOClZUxcM2H3UmXlwL", "4oGTdOClZUxcM2H3UmXlwL"),
    ("spotify:track:4oGTdOClZUxcM2H3UmXlwL", "4oGTdOClZUxcM2H3UmXlwL"),
    ("https://open.spotify.com/track/4oGTdOClZUxcM2H3UmXlwL", "4oGTdOClZUxcM2H3UmXlwL"),
    ("https://open.spotify.com/track/4oGTdOClZUxcM2H3UmXlwL?si=abc123def", "4oGTdOClZUxcM2H3UmXlwL"),
])
def test_normalize_spotify_id(input_id, expected):
    assert normalize_spotify_id(input_id) == expected


@pytest.mark.parametrize("bad_id", [
    "https://example.com/track/4oGTdOClZUxcM2H3UmXlwL",
    "foo:track:4oGTdOClZUxcM2H3UmXlwL",
])
def test_normalize_spotify_id_invalid(bad_id):
    with pytest.raises(ValueError):
        normalize_spotify_id(bad_id)


def test_spotify_track(rootdir):
    fp = Path(rootdir).joinpath("spotifytrack.json")
    track_json = json.loads(fp.read_text())
    track = SpotifyTrack(
        spotify_id=track_json["track"]["id"],
        name=track_json["track"]["name"],
        artist_name=track_json["track"]["artists"][0]["name"],
        uri=track_json["track"]["uri"],
    )
    track_history = SpotifyTrackHistory(
        spotify_id=track_json["track"]["id"],
        played_at=pendulum.parse(track_json["played_at"]),
    )
    assert track.name == "Always"
    assert track.artist_name == "Erasure"
    assert track_history.played_at.year == 2021
