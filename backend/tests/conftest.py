import json
import os
from pathlib import Path
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from mydiary.models import GoogleCalendarEvent, PocketArticle
from mydiary.googlecalendar_connector import MyDiaryGCal
from mydiary.pocket_connector import MyDiaryPocket
from mydiary.spotify_connector import MyDiarySpotify


@pytest.fixture
def rootdir() -> str:
    # path to tests directory
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(name="db_session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def loaded_db(rootdir: str, db_session: Session):
    datadir = Path(rootdir).joinpath("mydiary_day_data")

    gcal_events = json.loads(datadir.joinpath("gcal_events.json").read_text())
    for e in gcal_events:
        event = GoogleCalendarEvent.from_gcal_api_event(e)
        db_session.add(event)
    db_session.commit()

    pocket_articles_json = json.loads(
        datadir.joinpath("pocket_articles.json").read_text()
    )
    pocket_articles = [PocketArticle.from_pocket_item(a) for a in pocket_articles_json]
    mydiary_pocket = MyDiaryPocket()
    mydiary_pocket.save_articles_to_database(pocket_articles, session=db_session)

    spotify_tracks_json = json.loads(
        datadir.joinpath("spotify_tracks.json").read_text()
    )
    mydiary_spotify = MyDiarySpotify()
    for t in spotify_tracks_json:
        mydiary_spotify.save_one_track_to_database(t, session=db_session, commit=False)
    db_session.commit()

    yield db_session


@pytest.fixture
def note_body(rootdir: str):
    yield Path(rootdir).joinpath("test_mydiaryday_20221102.md").read_text()


# TODO: build MyDiaryDay from 2024-10-19
