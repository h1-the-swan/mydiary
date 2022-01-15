import os, json
from pathlib import Path
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.models import PocketArticle, PocketStatusEnum

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
    print(joplin_client)
    assert joplin_client.token is not None
    assert joplin_client.token != ""


def test_server_is_running(joplin_client: MyDiaryJoplin):
    print(joplin_client)
    assert joplin_client.server_is_running()
    print(joplin_client)