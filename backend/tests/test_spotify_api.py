# -*- coding: utf-8 -*-

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from spotipy.oauth2 import SpotifyOauthError

import mydiary.api
from mydiary.api import app, get_mydiary_spotify_or_none, get_session
from mydiary.models import PerformSong, SpotifyTrack
from mydiary.spotify_connector import (
    MyDiarySpotify,
    SpotifyTrackNotFound,
    SpotifyUnavailable,
    TrackSummary,
    normalize_spotify_id,
)


def raw_track(spotify_id, name, artists, album=None):
    # the parts of a Spotify API track dict that the app reads
    return {
        "id": spotify_id,
        "name": name,
        "uri": f"spotify:track:{spotify_id}",
        "artists": [{"name": a} for a in artists],
        "album": album or {},
    }


LANTERNS_TRACK = raw_track(
    "0FakeTrackLanterns0000",
    "Paper Lanterns",
    ["The Invented Band", "Guest Singer"],
    album={
        "name": "Made-Up Album (Live)",
        "release_date": "2011-04-01",
        "images": [
            {"url": "https://example.com/lanterns-640.jpg", "width": 640},
            {"url": "https://example.com/lanterns-64.jpg", "width": 64},
        ],
    },
)
ORCHARD_TRACK = raw_track("0FakeTrackOrchard00000", "Quiet Orchard", ["The Invented Band"])
LANTERNS = TrackSummary.from_track(LANTERNS_TRACK)
ORCHARD = TrackSummary.from_track(ORCHARD_TRACK)
MISSING_ID = "0FakeTrackMissing00000"


class FakeSpotify(MyDiarySpotify):
    # the real connector with Spotify itself swapped out, so lookup_track and
    # the track-row upsert run for real
    def __init__(self, tracks=(LANTERNS_TRACK, ORCHARD_TRACK), error=None):
        self.tracks = {t["id"]: t for t in tracks}
        self.error = error
        self.calls = []

    def get_track(self, spotify_id):
        self.calls.append(("lookup", spotify_id))
        if self.error:
            raise self.error
        track_id = normalize_spotify_id(spotify_id.strip())
        if track_id not in self.tracks:
            raise SpotifyTrackNotFound(track_id)
        return self.tracks[track_id]

    def search_tracks(self, q, limit=10):
        self.calls.append(("search", q))
        if self.error:
            raise self.error
        return [TrackSummary.from_track(t) for t in self.tracks.values()]


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def fake_spotify():
    return FakeSpotify()


@pytest.fixture(name="client")
def client_fixture(session: Session, fake_spotify: FakeSpotify):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_mydiary_spotify_or_none] = lambda: fake_spotify
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_song(session, spotify_id, name="Paper Lanterns"):
    s = PerformSong(name=name, artist_name="The Invented Band", spotify_id=spotify_id)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


class TestLookupSpotifyTrack:
    def test_returns_summary(self, client):
        r = client.get("/spotify/tracks/lookup", params={"id": LANTERNS.spotify_id})
        assert r.status_code == 200, r.text
        assert r.json() == {**LANTERNS.model_dump(), "used_by_perform_song_id": None}

    def test_passes_url_to_connector(self, client, fake_spotify):
        url = f"https://open.spotify.com/track/{LANTERNS.spotify_id}"
        r = client.get("/spotify/tracks/lookup", params={"id": url})
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] == LANTERNS.spotify_id
        assert fake_spotify.calls == [("lookup", url)]

    def test_used_by_is_lowest_id(self, client, session):
        add_song(session, None, name="Not On Spotify")
        first = add_song(session, LANTERNS.spotify_id)
        add_song(session, LANTERNS.spotify_id, name="Paper Lanterns (acoustic)")
        add_song(session, ORCHARD.spotify_id, name="Quiet Orchard")
        r = client.get("/spotify/tracks/lookup", params={"id": LANTERNS.spotify_id})
        assert r.json()["used_by_perform_song_id"] == first.id

    def test_unknown_is_404(self, client):
        r = client.get("/spotify/tracks/lookup", params={"id": MISSING_ID})
        assert r.status_code == 404

    def test_unavailable_is_502(self, client, fake_spotify):
        fake_spotify.error = SpotifyUnavailable("no cached Spotify token")
        r = client.get("/spotify/tracks/lookup", params={"id": LANTERNS.spotify_id})
        assert r.status_code == 502

    def test_id_is_required(self, client):
        assert client.get("/spotify/tracks/lookup").status_code == 422

    def test_unconfigured_client_is_502(self, client, monkeypatch):
        def raise_oauth_error(*args, **kwargs):
            raise SpotifyOauthError("No client_id")

        del app.dependency_overrides[get_mydiary_spotify_or_none]
        monkeypatch.setattr(mydiary.api, "MyDiarySpotify", raise_oauth_error)
        r = client.get("/spotify/tracks/lookup", params={"id": LANTERNS.spotify_id})
        assert r.status_code == 502


class TestSearchSpotifyTracks:
    def test_returns_summaries_with_used_by(self, client, session, fake_spotify):
        song = add_song(session, ORCHARD.spotify_id, name="Quiet Orchard")
        r = client.get("/spotify/tracks/search", params={"q": "invented band"})
        assert r.status_code == 200, r.text
        assert [(t["spotify_id"], t["used_by_perform_song_id"]) for t in r.json()] == [
            (LANTERNS.spotify_id, None),
            (ORCHARD.spotify_id, song.id),
        ]
        assert fake_spotify.calls == [("search", "invented band")]

    def test_no_results(self, client, fake_spotify):
        fake_spotify.tracks = {}
        r = client.get("/spotify/tracks/search", params={"q": "nothing matches"})
        assert r.status_code == 200
        assert r.json() == []

    def test_unavailable_is_502(self, client, fake_spotify):
        fake_spotify.error = SpotifyUnavailable("timed out")
        r = client.get("/spotify/tracks/search", params={"q": "invented band"})
        assert r.status_code == 502


def all_songs(session):
    return session.exec(select(PerformSong)).all()


class TestCreatePerformSong:
    song = {"name": "Paper Lanterns", "artist_name": "The Invented Band"}

    @pytest.mark.parametrize("given", [None, "", "  "])
    def test_no_spotify_id(self, client, fake_spotify, given):
        # used to be a 500: the ID was normalized even when there wasn't one
        r = client.post("/performsongs/", json={**self.song, "spotify_id": given})
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] is None
        assert fake_spotify.calls == []

    def test_saves_track_row(self, client, session, fake_spotify):
        url = f"https://open.spotify.com/track/{LANTERNS.spotify_id}?si=abc"
        r = client.post("/performsongs/", json={**self.song, "spotify_id": url})
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] == LANTERNS.spotify_id
        assert fake_spotify.calls == [("lookup", LANTERNS.spotify_id)]
        track = session.get(SpotifyTrack, LANTERNS.spotify_id)
        assert (track.name, track.artist_name) == (LANTERNS.name, LANTERNS.artist_name)

    @pytest.mark.parametrize(
        "given",
        [
            f"spotify:track:{LANTERNS.spotify_id}",
            f"https://open.spotify.com/intl-de/track/{LANTERNS.spotify_id}",
        ],
    )
    def test_track_uri_and_link_forms(self, client, fake_spotify, given):
        r = client.post("/performsongs/", json={**self.song, "spotify_id": given})
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] == LANTERNS.spotify_id

    def test_updates_existing_track_row(self, client, session):
        session.add(SpotifyTrack(spotify_id=ORCHARD.spotify_id, name="Old Name", artist_name="x", uri="u"))
        session.commit()
        r = client.post("/performsongs/", json={**self.song, "spotify_id": ORCHARD.spotify_id})
        assert r.status_code == 200, r.text
        assert session.get(SpotifyTrack, ORCHARD.spotify_id).name == ORCHARD.name

    def test_unknown_id_is_422(self, client, session):
        r = client.post("/performsongs/", json={**self.song, "spotify_id": MISSING_ID})
        assert r.status_code == 422
        assert r.json()["detail"][0]["loc"] == ["body", "spotify_id"]
        assert all_songs(session) == []

    @pytest.mark.parametrize(
        "given",
        [
            "https://example.com/track/1",
            "https://spotify.link/aBcD1234",
            # no scheme: normalize_spotify_id passes it through untouched
            "open.spotify.com/track/0FakeTrackLanterns0000",
            # right shape, but not a track: stored as is if Spotify can't check
            "https://open.spotify.com/album/0FakeTrackLanterns0000",
            "https://open.spotify.com/artist/0FakeTrackLanterns0000?si=x",
            "spotify:album:0FakeTrackLanterns0000",
        ],
    )
    def test_not_a_spotify_track_id_is_422(self, client, session, fake_spotify, given):
        r = client.post("/performsongs/", json={**self.song, "spotify_id": given})
        assert r.status_code == 422
        assert r.json()["detail"][0]["loc"] == ["body", "spotify_id"]
        assert fake_spotify.calls == []
        assert all_songs(session) == []

    def test_unavailable_saves_without_track_row(self, client, session, fake_spotify):
        fake_spotify.error = SpotifyUnavailable("timed out")
        r = client.post("/performsongs/", json={**self.song, "spotify_id": LANTERNS.spotify_id})
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] == LANTERNS.spotify_id
        assert session.get(SpotifyTrack, LANTERNS.spotify_id) is None

    def test_unconfigured_saves_without_track_row(self, client, session):
        app.dependency_overrides[get_mydiary_spotify_or_none] = lambda: None
        r = client.post("/performsongs/", json={**self.song, "spotify_id": LANTERNS.spotify_id})
        assert r.status_code == 200, r.text
        assert session.get(SpotifyTrack, LANTERNS.spotify_id) is None


class TestUpdatePerformSong:
    def patch(self, client, song, **data):
        return client.patch(f"/performsongs/{song.id}", json=data)

    def test_change_id_saves_track_row(self, client, session, fake_spotify):
        song = add_song(session, None)
        r = self.patch(client, song, spotify_id=f"spotify:track:{ORCHARD.spotify_id}")
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] == ORCHARD.spotify_id
        assert session.get(SpotifyTrack, ORCHARD.spotify_id) is not None

    def test_change_to_unknown_id_is_422(self, client, session):
        song = add_song(session, LANTERNS.spotify_id)
        r = self.patch(client, song, spotify_id=MISSING_ID, name="Renamed")
        assert r.status_code == 422
        assert r.json()["detail"][0]["loc"] == ["body", "spotify_id"]
        session.refresh(song)
        assert (song.spotify_id, song.name) == (LANTERNS.spotify_id, "Paper Lanterns")

    def test_unchanged_id_with_track_row_skips_spotify(self, client, session, fake_spotify):
        song = add_song(session, LANTERNS.spotify_id)
        session.add(SpotifyTrack.from_spotify_track(LANTERNS_TRACK))
        session.commit()
        r = self.patch(client, song, spotify_id=LANTERNS.spotify_id, notes="capo 2")
        assert r.status_code == 200, r.text
        assert fake_spotify.calls == []

    def test_unchanged_id_fills_missing_track_row(self, client, session):
        song = add_song(session, LANTERNS.spotify_id)
        r = self.patch(client, song, spotify_id=LANTERNS.spotify_id)
        assert r.status_code == 200, r.text
        assert session.get(SpotifyTrack, LANTERNS.spotify_id) is not None

    def test_unchanged_id_gone_from_spotify_still_saves(self, client, session):
        song = add_song(session, MISSING_ID)
        r = self.patch(client, song, spotify_id=MISSING_ID, notes="still learning")
        assert r.status_code == 200, r.text
        assert r.json()["notes"] == "still learning"

    @pytest.mark.parametrize("given", [None, ""])
    def test_clear_id(self, client, session, fake_spotify, given):
        song = add_song(session, LANTERNS.spotify_id)
        r = self.patch(client, song, spotify_id=given)
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] is None
        assert fake_spotify.calls == []

    def test_id_not_sent_skips_spotify(self, client, session, fake_spotify):
        song = add_song(session, LANTERNS.spotify_id)
        r = self.patch(client, song, notes="capo 2")
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] == LANTERNS.spotify_id
        assert fake_spotify.calls == []

    def test_unavailable_still_saves(self, client, session, fake_spotify):
        song = add_song(session, None)
        fake_spotify.error = SpotifyUnavailable("rate limited")
        r = self.patch(client, song, spotify_id=ORCHARD.spotify_id)
        assert r.status_code == 200, r.text
        assert r.json()["spotify_id"] == ORCHARD.spotify_id
