import os, json
from pathlib import Path
from mydiary.models import PocketArticle

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def test_env_loaded():
    assert "POCKET_CONSUMER_KEY" in os.environ
    assert "POCKET_ACCESS_TOKEN" in os.environ


# def test_spotify_api_call():
#     scopes = ["user-library-read", "user-read-recently-played", "user-top-read"]
#     sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scopes))
#     r = sp.current_user_recently_played()
#     assert 'items' in r


def test_spotify_track(rootdir):
    fp = Path(rootdir).joinpath("pocketitem.json")
    item_json = json.loads(fp.read_text())
    item = PocketArticle(
        id=item_json["resolved_id"],
        given_title=item_json["given_title"],
        resolved_title=item_json["resolved_title"],
        url=item_json["resolved_url"],
    )
    assert item.id == "3496035100"
    assert item.given_title == "Walmart will no longer sell toy cactus that raps about cocaine in Polish"
    assert item.url == "https://www.avclub.com/a-dancing-cactus-toy-that-raps-in-polish-about-cocaine-1848149902"
