import json
import uuid
import logging
from pathlib import Path
from mydiary.spotify_connector import MyDiarySpotify
import pendulum
import pytest

# from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from mydiary.models import Dog, GoogleCalendarEvent, PocketArticle, PocketStatusEnum, Tag, SpotifyTrackHistory


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
    spotify_track_history = SpotifyTrackHistory.from_spotify_track(track_json)
    # db_track_history = SpotifyTrackHistory.from_orm(spotify_track_history)
    db_session.add(spotify_track_history)
    MyDiarySpotify().add_or_update_track_in_database(track_json, session=db_session, commit=False)
    db_session.commit()
    db_session.refresh(spotify_track_history)

    assert track_json["track"]["id"] == spotify_track_history.spotify_id
    assert track_json["track"]["id"] == spotify_track_history.track.spotify_id
    assert track_json["track"]["name"] == spotify_track_history.track.name
    assert pendulum.parser.parse(track_json["played_at"]) == pendulum.instance(
        spotify_track_history.played_at
    )


def test_add_dog_to_database(rootdir: str, db_session: Session):
    dog = Dog(
        name="Ruffles",
    )
    db_session.add(dog)
    db_session.commit()

    db_dog = db_session.exec(select(Dog).where(Dog.name == "Ruffles")).one()
    assert db_dog.id == 1
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


def test_add_pocket_article_to_database(rootdir: str, db_session: Session):
    fp = Path(rootdir).joinpath("pocketitem.json")
    article_json = json.loads(fp.read_text())
    article = PocketArticle.from_pocket_item(article_json)
    article.collect_tags(db_session)
    db_session.add(article)
    db_session.commit()

    db_article = db_session.get(PocketArticle, article.id)
    assert db_article.status == PocketStatusEnum.UNREAD
    assert db_article.favorite is False
    assert db_article.word_count == 398
    assert db_article.listen_duration_estimate == 154
    assert db_article.time_added.year == 2021

    tag_names = [tag.name for tag in db_article.tags]
    assert "internet" in tag_names
    assert "news" in tag_names
    assert "quickbites" in tag_names

def test_add_pocket_article_existing_tag(rootdir: str, db_session: Session):
    fp = Path(rootdir).joinpath("pocketitem.json")

    tag_1 = Tag(name="internet")
    tag_2 = Tag(name="news")
    db_session.add(tag_1)
    db_session.add(tag_2)
    db_session.commit()

    db_tags = db_session.exec(select(Tag)).all()
    assert len(db_tags) == 2

    article_json = json.loads(fp.read_text())
    article = PocketArticle.from_pocket_item(article_json)
    article.collect_tags(db_session)
    db_session.add(article)
    db_session.commit()

    db_tags = db_session.exec(select(Tag)).all()
    assert len(db_tags) == 3

    db_article = db_session.get(PocketArticle, article.id)

    assert len(db_article.tags) == 3
    for tag in db_article.tags:
        assert tag.is_pocket_tag

    for t in [tag_1, tag_2]:
        tag_select = [tag for tag in db_article.tags if tag.name == t.name]
        assert len(tag_select) == 1
        assert tag_select[0].name == t.name

def test_add_tags(caplog, db_session: Session):
    caplog.set_level(logging.DEBUG)
    n = 10
    for i in range(n):
        tag = Tag(name="test tag")
        db_session.add(tag)
        db_session.commit()

    db_tags = db_session.exec(select(Tag)).all()
    assert len(db_tags) == n
