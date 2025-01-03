import json
import os
from pathlib import Path
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from mydiary.models import GoogleCalendarEvent, PocketArticle, MyDiaryWords
from mydiary.googlecalendar_connector import MyDiaryGCal
from mydiary.pocket_connector import MyDiaryPocket
from mydiary.spotify_connector import MyDiarySpotify
from mydiary.joplin_connector import MyDiaryJoplin

JOPLIN_TEST_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"


@pytest.fixture(scope="session")
def joplin_client():
    # with scope="session": the instance is shared across tests (so only initialized once)
    with MyDiaryJoplin(init_config=False, notebook_id=JOPLIN_TEST_NOTEBOOK_ID) as j:
        yield j


@pytest.fixture
def resource(joplin_client: MyDiaryJoplin):
    created_resources = []

    def _create_resource(data: bytes):
        r = joplin_client.create_resource(data=data)
        resource_id = r.json()["id"]
        created_resources.append(resource_id)
        return r

    yield _create_resource
    for resource_id in created_resources:
        joplin_client.delete_resource(resource_id, force=True)


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

    words = MyDiaryWords.from_txt(txt="Test words.", title="2024-10-19")
    db_session.add(words)
    db_session.commit()

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
        # TODO: mock or bypass spotify api call
        mydiary_spotify.save_one_track_to_database(t, session=db_session, commit=False)
    db_session.commit()

    yield db_session


@pytest.fixture
def note_body(rootdir: str):
    yield Path(rootdir).joinpath("test_mydiaryday_20221102.md").read_text()
