# -*- coding: utf-8 -*-

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from mydiary.api import app, get_session
from mydiary.models import PerformSong

SHEET = "[Verse 1]\n[C]Paper lanterns [G]on the line\n\n[Chorus]\n[F]Hold the light"


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def song(session: Session) -> PerformSong:
    s = PerformSong(name="Paper Lanterns", artist_name="The Invented Band", learned=False, key="Ab", capo=8)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def create_guitar(client, song):
    r = client.post(
        f"/performsongs/{song.id}/arrangements",
        json={"instrument": "guitar", "sheet": SHEET, "source": "paste"},
    )
    assert r.status_code == 200, r.text
    return r.json()


class TestArrangementRoutes:
    def test_create_list_read(self, client, song):
        arr = create_guitar(client, song)
        assert (arr["key"], arr["capo"], arr["source"]) == ("Ab", 8, "paste")
        listed = client.get(f"/performsongs/{song.id}/arrangements").json()
        assert [a["id"] for a in listed] == [arr["id"]]
        assert client.get(f"/arrangements/{arr['id']}").json()["sheet"] == SHEET

    def test_duplicate_is_409(self, client, song):
        create_guitar(client, song)
        r = client.post(f"/performsongs/{song.id}/arrangements", json={"instrument": "guitar"})
        assert r.status_code == 409

    def test_bad_instrument_is_422(self, client, song):
        r = client.post(f"/performsongs/{song.id}/arrangements", json={"instrument": "banjo"})
        assert r.status_code == 422

    def test_missing_song_is_404(self, client):
        r = client.post("/performsongs/999/arrangements", json={"instrument": "guitar"})
        assert r.status_code == 404

    def test_patch_and_delete(self, client, song):
        arr = create_guitar(client, song)
        r = client.patch(f"/arrangements/{arr['id']}", json={"capo": 0, "key": "C"})
        assert (r.json()["key"], r.json()["capo"], r.json()["sheet"]) == ("C", 0, SHEET)
        assert client.delete(f"/arrangements/{arr['id']}").json() == {"ok": True}
        assert client.get(f"/arrangements/{arr['id']}").status_code == 404


class TestPracticeRoutes:
    def post_run(self, client, song, arrangement_id=None, stumble=False):
        return client.post(
            "/practice/runs",
            json={
                "perform_song_id": song.id,
                "arrangement_id": arrangement_id,
                "sections": [
                    {"section_key": "Verse 1", "stumbled": stumble},
                    {"section_key": "Chorus", "stumbled": False},
                ],
            },
        )

    def test_create_run_and_levels(self, client, song):
        arr = create_guitar(client, song)
        for _ in range(3):
            r = self.post_run(client, song, arr["id"])
            assert r.status_code == 200, r.text
        run = r.json()
        assert run["instrument"] == "guitar"
        assert [s["section_key"] for s in run["sections"]] == ["Verse 1", "Chorus"]
        levels = {l["section_key"]: l for l in client.get(f"/performsongs/{song.id}/practice/levels").json()}
        assert levels["Chorus"]["level"] == "letters"
        assert levels["Chorus"]["num_runs"] == 3

    def test_lyrics_only_run(self, client, song):
        run = self.post_run(client, song).json()
        assert run["arrangement_id"] is None and run["instrument"] is None

    def test_run_with_another_songs_arrangement_is_422(self, client, song, session):
        other = PerformSong(name="Other", learned=False)
        session.add(other)
        session.commit()
        arr = create_guitar(client, song)
        r = client.post(
            "/practice/runs",
            json={"perform_song_id": other.id, "arrangement_id": arr["id"], "sections": [{"section_key": "A"}]},
        )
        assert r.status_code == 422

    def test_run_without_sections_is_422(self, client, song):
        r = client.post("/practice/runs", json={"perform_song_id": song.id, "sections": []})
        assert r.status_code == 422

    def test_list_runs(self, client, song):
        self.post_run(client, song, stumble=True)
        runs = client.get(f"/performsongs/{song.id}/practice/runs").json()
        assert runs[0]["sections"][0] == {"section_key": "Verse 1", "stumbled": True}

    def test_override_set_and_clear(self, client, song):
        r = client.put(
            f"/performsongs/{song.id}/practice/levels",
            json={"section_key": "Bridge", "level": "memorized"},
        )
        assert {l["section_key"]: l["level"] for l in r.json()}["Bridge"] == "memorized"
        r = client.delete(f"/performsongs/{song.id}/practice/levels", params={"section_key": "Bridge"})
        assert "Bridge" not in {l["section_key"] for l in r.json()}

    def test_override_bad_level_is_422(self, client, song):
        r = client.put(
            f"/performsongs/{song.id}/practice/levels",
            json={"section_key": "Bridge", "level": "mostly"},
        )
        assert r.status_code == 422

    def test_rename(self, client, song):
        self.post_run(client, song)
        r = client.post(
            f"/performsongs/{song.id}/practice/rename",
            json={"from_key": "Verse 1", "to_key": "First verse"},
        )
        assert r.json() == {"moved": 1}

    def test_learning_queue(self, client, song, session):
        learned = PerformSong(name="Old Favourite", learned=True)
        never = PerformSong(name="Never Played", learned=False)
        session.add(learned)
        session.add(never)
        session.commit()
        create_guitar(client, song)
        self.post_run(client, song)
        rows = client.get("/practice/learning").json()
        # never practiced first, then oldest practiced; learned songs excluded
        assert [r["song"]["name"] for r in rows] == ["Never Played", "Paper Lanterns"]
        assert rows[1]["instruments"] == ["guitar"]
        assert rows[1]["sheet"] == SHEET
        assert rows[1]["last_practiced_at"] is not None
        assert rows[0]["sheet"] is None
