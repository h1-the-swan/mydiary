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


# lookup_track / search_tracks, with a fake spotipy client. Names and IDs are
# invented.

from unittest.mock import MagicMock
import requests
from spotipy import SpotifyException
from spotipy.oauth2 import SpotifyOauthError
from mydiary.spotify_connector import (
    MyDiarySpotify,
    SpotifyTrackNotFound,
    SpotifyUnavailable,
    TrackSummary,
)

FAKE_ID = "FakeTrackId00000000001"


def fake_track(spotify_id=FAKE_ID, name="Paper Lanterns", release_date="2003-05-12"):
    return {
        "id": spotify_id,
        "name": name,
        "uri": f"spotify:track:{spotify_id}",
        "artists": [{"name": "The Invented Band"}, {"name": "Guest Singer"}],
        "album": {
            "name": "Lanterns (Live)",
            "release_date": release_date,
            "images": [
                {"url": "https://img.example/640", "width": 640, "height": 640},
                {"url": "https://img.example/64", "width": 64, "height": 64},
                {"url": "https://img.example/300", "width": 300, "height": 300},
            ],
        },
    }


@pytest.fixture
def fake_sp():
    sp = MagicMock()
    sp.auth_manager = MagicMock()  # so MyDiarySpotify doesn't build a real one
    return sp


def test_track_summary_from_track():
    s = TrackSummary.from_track(fake_track())
    assert s.spotify_id == FAKE_ID
    assert s.name == "Paper Lanterns"
    assert s.artist_name == "The Invented Band, Guest Singer"
    assert s.album_name == "Lanterns (Live)"
    assert s.release_year == 2003
    assert s.thumbnail_url == "https://img.example/64"


@pytest.mark.parametrize("release_date,expected", [
    ("1999", 1999),
    ("1999-07", 1999),
    ("0000", None),
    ("", None),
    (None, None),
])
def test_track_summary_release_year(release_date, expected):
    assert TrackSummary.from_track(fake_track(release_date=release_date)).release_year == expected


def test_track_summary_no_album_images():
    t = fake_track()
    t["album"]["images"] = []
    assert TrackSummary.from_track(t).thumbnail_url is None


@pytest.mark.parametrize("given", [
    FAKE_ID,
    f"  {FAKE_ID}  ",
    f"spotify:track:{FAKE_ID}",
    f"https://open.spotify.com/track/{FAKE_ID}?si=abc123",
])
def test_lookup_track_normalizes_id(fake_sp, given):
    fake_sp.track.return_value = fake_track()
    s = MyDiarySpotify(sp=fake_sp).lookup_track(given)
    fake_sp.track.assert_called_once_with(FAKE_ID)
    assert s.name == "Paper Lanterns"


@pytest.mark.parametrize("status", [400, 404])
def test_lookup_track_not_found(fake_sp, status):
    fake_sp.track.side_effect = SpotifyException(status, -1, "no such track")
    with pytest.raises(SpotifyTrackNotFound):
        MyDiarySpotify(sp=fake_sp).lookup_track(FAKE_ID)


@pytest.mark.parametrize("given", ["https://example.com/track/abc", "", "   "])
def test_lookup_track_bad_id_is_not_found(fake_sp, given):
    with pytest.raises(SpotifyTrackNotFound):
        MyDiarySpotify(sp=fake_sp).lookup_track(given)
    fake_sp.track.assert_not_called()


@pytest.mark.parametrize("error", [
    SpotifyException(401, -1, "token expired"),
    SpotifyException(429, -1, "Max Retries"),
    SpotifyException(503, -1, "unavailable"),
    SpotifyOauthError("refresh failed"),
    requests.exceptions.ConnectionError("no network"),
    requests.exceptions.Timeout("slow"),
    EOFError(),
])
def test_lookup_track_unavailable(fake_sp, error):
    fake_sp.track.side_effect = error
    with pytest.raises(SpotifyUnavailable):
        MyDiarySpotify(sp=fake_sp).lookup_track(FAKE_ID)


def test_search_tracks(fake_sp):
    other_id = "FakeTrackId00000000002"
    fake_sp.search.return_value = {
        "tracks": {
            "items": [
                fake_track(),
                None,
                fake_track(spotify_id=other_id, name="Paper Lanterns (Remastered)"),
            ]
        }
    }
    results = MyDiarySpotify(sp=fake_sp).search_tracks("paper lanterns")
    fake_sp.search.assert_called_once_with("paper lanterns", limit=10, type="track")
    assert [r.spotify_id for r in results] == [FAKE_ID, other_id]


def test_search_tracks_empty_query(fake_sp):
    assert MyDiarySpotify(sp=fake_sp).search_tracks("   ") == []
    fake_sp.search.assert_not_called()


@pytest.mark.parametrize("error", [
    SpotifyException(400, -1, "bad query"),
    SpotifyException(503, -1, "unavailable"),
    SpotifyOauthError("refresh failed"),
    requests.exceptions.ConnectionError("no network"),
])
def test_search_tracks_unavailable(fake_sp, error):
    fake_sp.search.side_effect = error
    with pytest.raises(SpotifyUnavailable):
        MyDiarySpotify(sp=fake_sp).search_tracks("paper lanterns")


def test_lookup_track_empty_response_is_unavailable(fake_sp):
    fake_sp.track.return_value = None
    with pytest.raises(SpotifyUnavailable):
        MyDiarySpotify(sp=fake_sp).lookup_track(FAKE_ID)


def test_search_tracks_empty_response_is_unavailable(fake_sp):
    fake_sp.search.return_value = None
    with pytest.raises(SpotifyUnavailable):
        MyDiarySpotify(sp=fake_sp).search_tracks("paper lanterns")


def test_no_cached_token_is_unavailable(fake_sp):
    # without this check spotipy would prompt on stdin
    fake_sp.auth_manager.cache_handler.get_cached_token.return_value = None
    mydiary_spotify = MyDiarySpotify(sp=fake_sp)
    with pytest.raises(SpotifyUnavailable):
        mydiary_spotify.lookup_track(FAKE_ID)
    with pytest.raises(SpotifyUnavailable):
        mydiary_spotify.search_tracks("paper lanterns")
    fake_sp.track.assert_not_called()
    fake_sp.search.assert_not_called()
