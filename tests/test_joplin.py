import os, json
from pathlib import Path
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.models import PocketArticle, PocketStatusEnum, JoplinNote

from dotenv import load_dotenv, find_dotenv

import pytest

load_dotenv(find_dotenv())


@pytest.fixture(scope="session")
def joplin_client():
    # with scope="session": the instance is shared across tests (so only initialized once)
    with MyDiaryJoplin(init_config=False) as j:
        yield j


def test_env_loaded():
    assert "JOPLIN_AUTH_TOKEN" in os.environ
    # assert "JOPLIN_BASE_URL" in os.environ


def test_has_token(joplin_client: MyDiaryJoplin):
    assert joplin_client.token is not None
    assert joplin_client.token != ""


def test_server_is_running(joplin_client: MyDiaryJoplin):
    assert joplin_client.server_is_running()


def test_joplin_note_from_api(joplin_client: MyDiaryJoplin):
    note_id = "870912b332b547f2851ee6dbacf1ac85"
    note = joplin_client.get_note(note_id)
    assert note.title == "2021-12-27"
    parent_id = note.parent_id
    notebook = joplin_client.get_notebook(parent_id)
    assert notebook.title == "2021"
