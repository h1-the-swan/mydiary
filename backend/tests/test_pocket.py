import os, json
import pytest
import logging
from pathlib import Path

# from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from mydiary.models import PocketArticle, PocketStatusEnum, Tag, PocketArticleUpdate
from mydiary.pocket_connector import MyDiaryPocket

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


def test_env_loaded():
    assert "POCKET_CONSUMER_KEY" in os.environ
    assert "POCKET_ACCESS_TOKEN" in os.environ


@pytest.mark.external_api
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
    assert article.pocket_url == "https://getpocket.com/read/3496035100"
    assert (
        article.to_markdown()
        == "[A dancing cactus toy that raps in Polish about cocaine withdrawal has been pulled from sale](https://www.avclub.com/a-dancing-cactus-toy-that-raps-in-polish-about-cocaine-1848149902) ([Pocket link](https://getpocket.com/read/3496035100))"
    )

    # for t in article._pocket_item["tags"].values():
    #     tag = Tag(name=t["tag"], pocket_tag_id=t["item_id"])
    #     article.tags.append(tag)
    # article.collect_tags(db_session)
    tag_names = [tag.name for tag in article.tags]
    assert "internet" in tag_names
    assert "news" in tag_names
    assert "quickbites" in tag_names


def test_update_article(rootdir: str, db_session: Session):
    mydiary_pocket = MyDiaryPocket()
    raindrop_id = 917478042
    fp = Path(rootdir).joinpath("pocketitem.json")
    article_json = json.loads(fp.read_text())
    article = PocketArticle.from_pocket_item(article_json)
    article.raindrop_id = raindrop_id
    db_session.add(article)
    db_session.commit()

    fp2 = Path(rootdir).joinpath("pocketitemupdate.json")
    article_json = json.loads(fp2.read_text())
    assert "tagupdate" in article_json["tags"].keys()
    article_update = PocketArticleUpdate.model_validate(article_json)
    article_update.pocket_tags = list(article_json["tags"].keys())

    mydiary_pocket.update_article(
        db_article=article,
        article_update=article_update,
        session=db_session,
        post_commit=True,
    )

    db_article = db_session.get(PocketArticle, article.id)
    assert db_article.status == PocketStatusEnum.ARCHIVED
    assert db_article.favorite is False
    assert db_article.word_count == 398
    assert db_article.listen_duration_estimate == 154
    assert db_article.time_added.year == 2021
    assert db_article.time_added.day == 4
    assert db_article.time_read.day == 8
    assert db_article.raindrop_id == raindrop_id
    tag_names = [tag.name for tag in db_article.tags]
    assert "internet" in tag_names
    assert "news" in tag_names
    assert "quickbites" in tag_names
    assert "tagupdate" in tag_names
