import os, json
from pathlib import Path
from mydiary.models import PocketArticle, PocketStatusEnum

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def test_env_loaded():
    assert "JOPLIN_AUTH_TOKEN" in os.environ
    # assert "JOPLIN_BASE_URL" in os.environ
