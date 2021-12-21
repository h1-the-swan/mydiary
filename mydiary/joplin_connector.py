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


class MyDiaryJoplin:
    def __init__(
        self,
        token: Optional[str] = None,
        server_process: Optional[subprocess.Popen] = None,
    ) -> None:
        self.base_url = JOPLIN_BASE_URL
        self.token = token
        if not self.token:
            self.token = JOPLIN_AUTH_TOKEN
        self.server_process = server_process

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
