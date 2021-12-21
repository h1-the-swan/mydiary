import os, json
from pathlib import Path
from mydiary.models import GoogleCalendarEvent

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def test_env_loaded():
    assert "GOOGLECALENDAR_TOKEN_CACHE" in os.environ


def test_gcal_api_call():
    from mydiary.googlecalendar_connector import MyDiaryGCal
    # TODO
#     mydiary_pocket = MyDiaryPocket()
#     r = mydiary_pocket.pocket_instance.get(count=1)
#     assert len(r[0]['list']) == 1

# def test_pocket_article(rootdir):
#     fp = Path(rootdir).joinpath("pocketitem.json")
#     article_json = json.loads(fp.read_text())
#     article = PocketArticle.from_pocket_item(article_json)
#     assert article.status == PocketStatusEnum.UNREAD
#     assert article.favorite is False

    



