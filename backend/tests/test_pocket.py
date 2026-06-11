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


def _minimal_pocket_item(**overrides):
    base = {
        "item_id": 1,
        "given_title": "Given Title",
        "resolved_title": "Resolved Title",
        "resolved_url": "https://example.com/article",
        "favorite": "0",
        "status": "0",
        "time_added": "1609459200",
        "time_updated": "1609459200",
        "time_read": "0",
        "time_favorited": "0",
        "word_count": "500",
        "listen_duration_estimate": "193",
    }
    base.update(overrides)
    return base


def test_pocket_article_no_tags():
    item = _minimal_pocket_item()  # no "tags" key
    article = PocketArticle.from_pocket_item(item)
    assert article.tags == []

    item_empty_tags = _minimal_pocket_item(tags={})
    article2 = PocketArticle.from_pocket_item(item_empty_tags)
    assert article2.tags == []


def test_pocket_article_to_markdown_title_fallback():
    # resolved_title takes precedence when both are set
    item = _minimal_pocket_item(given_title="Given Title", resolved_title="Resolved Title")
    article = PocketArticle.from_pocket_item(item)
    md = article.to_markdown()
    assert "Resolved Title" in md
    assert "Given Title" not in md

    # falls back to given_title when resolved_title is empty
    item2 = _minimal_pocket_item(given_title="Given Title", resolved_title="")
    article2 = PocketArticle.from_pocket_item(item2)
    md2 = article2.to_markdown()
    assert "Given Title" in md2

    # falls back to "Unknown title" when both are empty
    item3 = _minimal_pocket_item(given_title="", resolved_title="")
    article3 = PocketArticle.from_pocket_item(item3)
    md3 = article3.to_markdown()
    assert "Unknown title" in md3
