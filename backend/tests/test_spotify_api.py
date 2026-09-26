# -*- coding: utf-8 -*-

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from spotipy.oauth2 import SpotifyOauthError

import mydiary.api
from mydiary.api import app, get_mydiary_spotify, get_session
from mydiary.models import PerformSong
from mydiary.spotify_connector import (
    SpotifyTrackNotFound,
    SpotifyUnavailable,
    TrackSummary,
)

LANTERNS = TrackSummary(
    spotify_id="0FakeTrackLanterns00000",
    name="Paper Lanterns",
    artist_name="The Invented Band, Guest Singer",
    album_name="Made-Up Album (Live)",
    release_year=2011,
    thumbnail_url="https://example.com/lanterns-64.jpg",
)
ORCHARD = TrackSummary(
    spotify_id="0FakeTrackOrchard000000",
    name="Quiet Orchard",
    artist_name="The Invented Band",
)


class FakeSpotify:
    def __init__(self, tracks=(LANTERNS, ORCHARD), error=None):
        self.tracks = {t.spotify_id: t for t in tracks}
        self.error = error
        self.calls = []

    def lookup_track(self, spotify_id):
        self.calls.append(("lookup", spotify_id))
        if self.error:
            raise self.error
        # stands in for the connector's normalization of URLs
        track_id = spotify_id.rsplit("/", 1)[-1]
        if track_id not in self.tracks:
            raise SpotifyTrackNotFound(track_id)
        return self.tracks[track_id]

    def search_tracks(self, q, limit=10):
        self.calls.append(("search", q))
        if self.error:
            raise self.error
        return list(self.tracks.values())


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
    app.dependency_overrides[get_mydiary_spotify] = lambda: fake_spotify
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
        r = client.get("/spotify/tracks/lookup", params={"id": "0FakeTrackMissing000000"})
        assert r.status_code == 404

    def test_unavailable_is_502(self, client, fake_spotify):
        fake_spotify.error = SpotifyUnavailable("no cached Spotify token")
        r = client.get("/spotify/tracks/lookup", params={"id": LANTERNS.spotify_id})
        assert r.status_code == 502

    def test_id_is_required(self, client):
        assert client.get("/spotify/tracks/lookup").status_code == 422

    def test_unconfigured_client_is_502(self, client, monkeypatch):
        def raise_oauth_error():
            raise SpotifyOauthError("No client_id")

        del app.dependency_overrides[get_mydiary_spotify]
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
