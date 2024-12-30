import json
import uuid
import logging
import hashlib
from pathlib import Path
from mydiary.spotify_connector import MyDiarySpotify
import pendulum
import pytest

# from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from mydiary.models import (
    Dog,
    GoogleCalendarEvent,
    PocketArticle,
    PocketStatusEnum,
    Tag,
    SpotifyTrackHistory,
    JoplinNote,
    MyDiaryImage,
    MyDiaryWords,
)
from mydiary.core import reduce_size_recurse


def test_add_spotify_track_history_to_database(rootdir: str, db_session: Session):
    fp = Path(rootdir).joinpath("spotifytrack.json")
    track_json = json.loads(fp.read_text())
    spotify_track_history = SpotifyTrackHistory.from_spotify_track(track_json)
    # db_track_history = SpotifyTrackHistory.from_orm(spotify_track_history)
    db_session.add(spotify_track_history)
    MyDiarySpotify().add_or_update_track_in_database(
        track_json, session=db_session, commit=False
    )
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


class TestPocketArticleDatabase:
    def test_add_pocket_article_to_database(self, rootdir: str, db_session: Session):
        fp = Path(rootdir).joinpath("pocketitem.json")
        article_json = json.loads(fp.read_text())
        article = PocketArticle.from_pocket_item(article_json)
        now = pendulum.now(tz="UTC")
        article.time_last_api_sync = now
        db_session.add(article)
        db_session.commit()

        db_article = db_session.get(PocketArticle, article.id)
        assert db_article.status == PocketStatusEnum.UNREAD
        assert db_article.favorite is False
        assert db_article.word_count == 398
        assert db_article.listen_duration_estimate == 154
        assert db_article.time_added.year == 2021
        assert db_article.time_last_api_sync.timestamp() == now.timestamp()

        tag_names = [tag.name for tag in db_article.tags]
        assert "internet" in tag_names
        assert "news" in tag_names
        assert "quickbites" in tag_names

    def test_add_pocket_article_existing_tag(self, rootdir: str, db_session: Session):
        tag_1 = Tag(name="internet")
        tag_2 = Tag(name="news")
        db_session.add(tag_1)
        db_session.add(tag_2)
        db_session.commit()

        db_tags = db_session.exec(select(Tag)).all()
        assert len(db_tags) == 2

        fp = Path(rootdir).joinpath("pocketitem.json")
        article_json = json.loads(fp.read_text())
        article = PocketArticle.from_pocket_item(article_json)
        db_session.merge(article)
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

    def test_add_tags(self, caplog: pytest.LogCaptureFixture, db_session: Session):
        caplog.set_level(logging.DEBUG)
        n = 10
        for i in range(n):
            tag = Tag(name=f"test tag {i}")
            db_session.add(tag)
            db_session.commit()

        db_tags = db_session.exec(select(Tag)).all()
        assert len(db_tags) == n

    # def test_update_article(self, rootdir: str, db_session: Session):
    #     raindrop_id = 917478042
    #     fp = Path(rootdir).joinpath("pocketitem.json")
    #     article_json = json.loads(fp.read_text())
    #     article = PocketArticle.from_pocket_item(article_json)
    #     article.raindrop_id = raindrop_id
    #     db_session.add(article)
    #     db_session.commit()

    #     fp2 = Path(rootdir).joinpath("pocketitemupdate.json")
    #     article_json = json.loads(fp2.read_text())
    #     article_update = PocketArticle.from_pocket_item(article_json)
    #     db_session.merge(article_update)
    #     # db_session.delete(article)
    #     # db_session.commit()
    #     # db_session.add(article_update)
    #     db_session.commit()

    #     db_article = db_session.get(PocketArticle, article.id)
    #     assert db_article.status == PocketStatusEnum.ARCHIVED
    #     assert db_article.favorite is False
    #     assert db_article.word_count == 398
    #     assert db_article.listen_duration_estimate == 154
    #     assert db_article.time_added.year == 2021
    #     assert db_article.time_added.day == 4
    #     assert db_article.time_read.day == 8
    #     assert db_article.raindrop_id == raindrop_id


class TestMyDiaryImage:
    JOPLIN_TEST_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"

    def test_add_thumbnail(self, rootdir: str, db_session: Session):
        fp = Path(rootdir).joinpath("images/24-05-18 13-50-28 9143.jpg")
        image_name = fp.stem
        image_bytes = fp.read_bytes()
        image_bytes = reduce_size_recurse(image_bytes, (512, 512), 60000)
        fmt = "YY-MM-DD HH-mm-ss SSSS"
        image_dt = pendulum.from_format(image_name, fmt, tz="America/New_York")
        image_hash = hashlib.md5()
        image_hash.update(image_bytes)
        nextcloud_path = "H1phone_sync/2024/05/24-05-18%2013-50-28%209143.jpg"
        mydiary_image = MyDiaryImage(
            hash=image_hash.hexdigest(),
            name=image_name,
            filepath=None,
            nextcloud_path=nextcloud_path,
            description=None,
            thumbnail_size=len(image_bytes),
            joplin_resource_id=None,
            created_at=image_dt.in_timezone("UTC"),
        )
        db_session.add(mydiary_image)
        db_session.commit()

        db_image = db_session.exec(
            select(MyDiaryImage).where(MyDiaryImage.hash == image_hash.hexdigest())
        ).one()
        assert db_image.id == 1
        assert db_image.hash == image_hash.hexdigest()
        assert db_image.nextcloud_path == nextcloud_path
        assert db_image.thumbnail_size == len(image_bytes)
        assert db_image.thumbnail_size < 60000
        db_image_dt = pendulum.instance(db_image.created_at, tz="UTC")
        assert db_image_dt == image_dt


class TestMyDiaryWords:
    def test_add_words(self, db_session: Session):
        note_id = "d1f21d74ccc243388735a2c6779cd428"
        note_title = "2022-01-14"
        txt = (
            """Today I tested the "mydiarywords" table in the database.\n\nIt worked."""
        )
        hash = hashlib.md5()
        hash.update(txt.encode("utf-8"))
        now = pendulum.now().in_timezone("UTC")
        mydiary_words = MyDiaryWords(
            joplin_note_id=note_id,
            note_title=note_title,
            txt=txt,
            created_at=now,
            updated_at=now,
            hash=hash.hexdigest(),
        )
        db_session.add(mydiary_words)
        db_session.commit()

        db_words = db_session.exec(
            select(MyDiaryWords).where(MyDiaryWords.joplin_note_id == note_id)
        ).one()
        assert db_words.id == 1
        assert db_words.hash == hash.hexdigest()
        assert db_words.joplin_note_id == note_id
        assert db_words.note_title == note_title
        assert db_words.txt == txt
        assert db_words.created_at.timestamp() == now.timestamp()
        assert db_words.updated_at.timestamp() == now.timestamp()


class TestJoplinNoteDatabase:
    JOPLIN_TEST_NOTEBOOK_ID = "08f4b0d7218148ae97b4c6003d85b16a"

    def test_add_note(self, db_session: Session, note_body: str):
        now = pendulum.now().in_timezone("UTC")
        note_id = "8dde7cc9e9484721b713bdc8c1ae30c2"
        joplin_note = JoplinNote(
            id=note_id,
            parent_id=self.JOPLIN_TEST_NOTEBOOK_ID,
            title="2022-11-02",
            body=note_body,
            created_time=now,
            updated_time=now,
        )
        # words_txt = joplin_note.md_note.get_section_by_title("words").get_content()
        # hash = hashlib.md5()
        # hash.update(words_txt.encode("utf-8"))
        # words = MyDiaryWords(
        #     joplin_note_id=note_id,
        #     joplin_note_title="2022-11-02",
        #     txt=words_txt,
        #     created_at=now,
        #     updated_at=now,
        #     hash=hash.hexdigest(),
        # )
        words = MyDiaryWords.from_joplin_note(joplin_note)
        db_session.add(joplin_note)
        db_session.add(words)
        db_session.commit()

        db_note = db_session.exec(
            select(JoplinNote).where(JoplinNote.id == note_id)
        ).one()
        assert db_note.id == note_id
        assert db_note.parent_id == self.JOPLIN_TEST_NOTEBOOK_ID
        assert db_note.title == "2022-11-02"
        assert db_note.body == note_body
        assert db_note.created_time.timestamp() == now.timestamp()
        assert db_note.updated_time.timestamp() == now.timestamp()

        assert db_note.words.joplin_note_id == note_id
        assert db_note.words.note_title == "2022-11-02"
        words_txt = joplin_note.md_note.get_section_by_title("words").get_content()
        assert db_note.words.txt == words_txt
        assert db_note.words.created_at.timestamp() == now.timestamp()
        assert db_note.words.updated_at.timestamp() == now.timestamp()
        hash = hashlib.md5()
        hash.update(words_txt.encode("utf-8"))
        assert db_note.words.hash == hash.hexdigest()


def test_loaded_db(loaded_db: Session):
    db_words = loaded_db.exec(select(MyDiaryWords)).all()
    assert len(db_words) == 1
    assert db_words[0].note_title == "2024-10-19"

    db_events = loaded_db.exec(select(GoogleCalendarEvent)).all()
    assert len(db_events) == 2

    db_pocket_articles = loaded_db.exec(select(PocketArticle)).all()
    assert len(db_pocket_articles) == 5

    db_spotify_tracks = loaded_db.exec(select(SpotifyTrackHistory)).all()
    assert len(db_spotify_tracks) == 13
