import os, json
from pathlib import Path

import pendulum
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.models import PocketArticle, PocketStatusEnum, JoplinNote

# from dotenv import load_dotenv, find_dotenv

import pytest

# load_dotenv(find_dotenv())

JOPLIN_TEST_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"


@pytest.fixture(scope="session")
def joplin_client():
    # with scope="session": the instance is shared across tests (so only initialized once)
    with MyDiaryJoplin(init_config=False, notebook_id=JOPLIN_TEST_NOTEBOOK_ID) as j:
        yield j


@pytest.fixture
def resource(joplin_client: MyDiaryJoplin):
    created_resources = []

    def _create_resource(data: bytes):
        r = joplin_client.create_resource(data=data)
        resource_id = r.json()["id"]
        created_resources.append(resource_id)
        return r

    yield _create_resource
    for resource_id in created_resources:
        joplin_client.delete_resource(resource_id, force=True)


@pytest.fixture
def image_bytes(rootdir):
    fp = Path(rootdir).joinpath("images/22-04-28 17-20-37 4351.jpg")
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
