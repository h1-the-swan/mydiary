import os, json
import pytest
import logging
from pathlib import Path

# from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from mydiary.models import PocketArticle, PocketStatusEnum, Tag

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


@pytest.fixture(name="db_session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_env_loaded():
    assert "POCKET_CONSUMER_KEY" in os.environ
    assert "POCKET_ACCESS_TOKEN" in os.environ


def test_pocket_api_call():
    from mydiary.pocket_connector import MyDiaryPocket

    mydiary_pocket = MyDiaryPocket()
    r = mydiary_pocket.pocket_instance.get(count=1)
    assert len(r[0]["list"]) == 1


def test_pocket_article(rootdir, caplog, db_session: Session):
    caplog.set_level(logging.DEBUG)
    fp = Path(rootdir).joinpath("pocketitem.json")
    article_json = json.loads(fp.read_text())
    article = PocketArticle.from_pocket_item(article_json)
    assert article.status == PocketStatusEnum.UNREAD
    assert article.favorite is False
    assert article.word_count == 398
    assert article.listen_duration_estimate == 154
    assert article.time_added.year == 2021

    # for t in article._pocket_item["tags"].values():
    #     tag = Tag(name=t["tag"], pocket_tag_id=t["item_id"])
    #     article.tags.append(tag)
    article.collect_tags(db_session)
    tag_names = [tag.name for tag in article.tags]
    assert "internet" in tag_names
    assert "news" in tag_names
    assert "quickbites" in tag_names
