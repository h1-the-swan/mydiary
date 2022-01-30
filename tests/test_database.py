import json
import uuid
from pathlib import Path
import pendulum
import pytest

# from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from mydiary.spotify_history import SpotifyTrackHistory, SpotifyTrackHistoryCreate
from mydiary.models import Dog, GoogleCalendarEvent


@pytest.fixture(name="db_session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_add_spotify_track_history_to_database(rootdir: str, db_session: Session):
    fp = Path(rootdir).joinpath("spotifytrack.json")
    track_json = json.loads(fp.read_text())
    spotify_track = SpotifyTrackHistoryCreate.from_spotify_track(track_json)
    db_track = SpotifyTrackHistory.from_orm(spotify_track)
    db_session.add(db_track)
    db_session.commit()
    db_session.refresh(db_track)

    assert track_json["track"]["id"] == db_track.spotify_id
    assert track_json["track"]["name"] == db_track.name
    assert pendulum.parser.parse(track_json["played_at"]) == pendulum.instance(
        db_track.played_at
    )


def test_add_dog_to_database(rootdir: str, db_session: Session):
    uid = uuid.uuid4()
    dog = Dog(
        uid=uid,
        name="Ruffles",
    )
    db_session.add(dog)
    db_session.commit()

    db_dog = db_session.get(Dog, uid)
    assert db_dog.uid == uid
    assert db_dog.name == "Ruffles"


def test_add_gcal_event_to_database(rootdir: str, db_session: Session):
    fp = Path(rootdir).joinpath("gcalevent.json")
    article_json = json.loads(fp.read_text())
    event = GoogleCalendarEvent.from_gcal_api_event(article_json)
    db_session.add(event)
    db_session.commit()

    db_event = db_session.get(GoogleCalendarEvent, event.id)
    assert db_event.summary == "Holiday in the Park!"
    assert db_event.description is not None
    assert len(db_event.description) > 1000
    assert "seattle" in db_event.location.lower()
    assert db_event.start == event.start
    assert db_event.end == event.end
