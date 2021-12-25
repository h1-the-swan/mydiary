# -*- coding: utf-8 -*-

DESCRIPTION = """Joplin API (local instance)"""

import sys, os, time
import requests
import subprocess
from pathlib import Path
from datetime import date, datetime
import pendulum
from timeit import default_timer as timer
from typing import Any, Dict, List, Optional

from mydiary.models import JoplinNote

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

JOPLIN_BASE_URL = os.environ.get("JOPLIN_BASE_URL") or "http://localhost:41184"
JOPLIN_AUTH_TOKEN = os.environ["JOPLIN_AUTH_TOKEN"]

# for testing purposes. we'll probably want to get this from an environment variable.
JOPLIN_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"

def title_from_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

class MyDiaryJoplin:
    def __init__(
        self,
        token: Optional[str] = None,
        server_process: Optional[subprocess.Popen] = None,
        notebook_id: str = JOPLIN_NOTEBOOK_ID,
    ) -> None:
        self.base_url = JOPLIN_BASE_URL
        self.token = token
        if not self.token:
            self.token = JOPLIN_AUTH_TOKEN
        self.server_process = server_process
        self.notebook_id = notebook_id

    def __enter__(self) -> 'MyDiaryJoplin':
        """This allows this class to be used as a context manager.

        ```
        with MyDiaryJoplin() as mj:
            mj.get_note(note_id)
        ```
        """        
        if not self.server_is_running():
            self.start_server()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is called after the context manager ends
        self.teardown()

    def server_is_running(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/ping")
        except requests.ConnectionError:
            return False
        return r.ok

    def start_server(self) -> None:
        self.server_process = subprocess.Popen(
            ["joplin", "server", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

    def teardown(self) -> None:
        if self.server_process is not None:
            self.server_process.terminate()

    def sync(self, quiet=True, timeout: int = 20) -> None:
        # TODO better handling of failure (e.g., if nextcloud is not running, or if the ip is misconfigured)
        if quiet is True:
            _stdout = subprocess.DEVNULL
        else:
            _stdout = None
        subprocess.run(
            ["joplin", "sync"],
            stdout=_stdout,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )

    def post_note(self, data: Dict[str, Any]):
        return requests.post(
            f"{self.base_url}/notes", json=data, params={"token": self.token}
        )

    def get_note_id_by_title(self, title) -> str:
        params = {
            "token": self.token,
            "query": f'title:"{title}"',
        }
        r = requests.get(f"{self.base_url}/search", params=params)
        items = r.json()["items"]
        if not items:
            return None
        items = [item for item in items if item["parent_id"] == self.notebook_id]
        if not items:
            return None
        if len(items) > 1:
            raise RuntimeError(f"more than one note found with title {title}")
        return items[0]["id"]

    def get_note_id_by_date(self, dt: datetime) -> str:
        title = title_from_date(dt)
        return self.get_note_id_by_title(title)

    def get_note(self, id: str) -> JoplinNote:
        fields = [
            "id",
            "parent_id",
            "title",
            "body",
            "created_time",
            "updated_time",
        ]
        params = {
            "token": self.token,
            "fields": fields,
        }
        r = requests.get(f"{self.base_url}/notes/{id}", params=params)
        return JoplinNote.from_api_response(r)
