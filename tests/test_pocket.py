import os, json
from pathlib import Path
from mydiary.models import PocketArticle, PocketStatusEnum

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def test_env_loaded():
    assert "POCKET_CONSUMER_KEY" in os.environ
    assert "POCKET_ACCESS_TOKEN" in os.environ


def test_pocket_api_call():
    from mydiary.pocket_connector import MyDiaryPocket
    mydiary_pocket = MyDiaryPocket()
    r = mydiary_pocket.pocket_instance.get(count=1)
    assert len(r[0]['list']) == 1

def test_api_article(rootdir):
    fp = Path(rootdir).joinpath("pocketitem.json")
    article_json = json.loads(fp.read_text())
    article = PocketArticle.from_pocket_item(article_json)
    assert article.status == PocketStatusEnum.UNREAD
    assert article.favorite is False

    


