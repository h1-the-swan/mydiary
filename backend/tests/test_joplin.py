import os, json
from pathlib import Path

import pendulum
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.models import PocketArticle, PocketStatusEnum, JoplinNote

# from dotenv import load_dotenv, find_dotenv

import pytest

# load_dotenv(find_dotenv())


@pytest.fixture
def image_bytes(rootdir):
    fp = Path(rootdir).joinpath("images/24-05-18 13-50-28 9143.jpg")
    image_bytes = fp.read_bytes()
    yield image_bytes


def test_env_loaded():
    assert "JOPLIN_AUTH_TOKEN" in os.environ
    # assert "JOPLIN_BASE_URL" in os.environ


def test_has_token(joplin_client: MyDiaryJoplin):
    assert joplin_client.token is not None
    assert joplin_client.token != ""


def test_server_is_running(joplin_client: MyDiaryJoplin):
    assert joplin_client.server_is_running()


def test_joplin_note_from_api(joplin_client: MyDiaryJoplin):
    dt_str = "2022-01-14"
    dt = pendulum.parse(dt_str)
    note_id = joplin_client.get_note_id_by_date(dt)
    assert note_id == "d1f21d74ccc243388735a2c6779cd428"
    note = joplin_client.get_note(note_id)
    assert note.title == dt_str
    parent_id = note.parent_id
    notebook = joplin_client.get_notebook(parent_id)
    assert notebook.title == "2022"


def test_create_resource(resource, image_bytes):
    r = resource(image_bytes)
    j = r.json()
    assert j["id"] is not None
    assert len(j["id"]) > 0
