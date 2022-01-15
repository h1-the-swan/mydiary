# -*- coding: utf-8 -*-

DESCRIPTION = """Joplin API (local instance)"""

import sys, os, time, json, re
import requests
import subprocess
import hashlib
from pathlib import Path
from datetime import date, datetime
from time import sleep
import pendulum
from timeit import default_timer as timer
from typing import Any, Dict, List, Optional, Tuple, Union

from .core import reduce_image_size
from .models import JoplinNote, JoplinFolder

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
# JOPLIN_NOTEBOOK_ID = "b2494842bba94ef3b429f682c4e3386f"

JOPLIN_CONFIG = {
    "locale": "en_US",
    "dateFormat": "YYYY-MM-DD",
    "timeFormat": "HH:mm",
}


def title_from_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


class MyDiaryJoplin:
    def __init__(
        self,
        token: Optional[str] = None,
        server_process: Optional[subprocess.Popen] = None,
        notebook_id: str = JOPLIN_NOTEBOOK_ID,
        init_config: bool = True,
        # quiet: bool = True,
        last_sync: Optional[pendulum.DateTime] = None,
    ) -> None:
        # ! Don't use more than one level of subnotebooks (i.e., don't use subsubnotebooks). it's hard to work with.
        # subnotebooks are by year (so each will contain 365-366 diary entries)
        self.base_url = JOPLIN_BASE_URL
        self.token = token
        if not self.token:
            self.token = JOPLIN_AUTH_TOKEN
        self.server_process = server_process
        self.notebook_id = notebook_id
        # self.quiet = quiet
        self.last_sync = last_sync

        if init_config is True:
            self.config()

        self._parent_notebook = None  # lazy loading. see property below

    def __enter__(self) -> "MyDiaryJoplin":
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

    @property
    def parent_notebook(self) -> JoplinFolder:
        if self._parent_notebook is None:
            self._parent_notebook = self.get_notebook(self.notebook_id)
        return self._parent_notebook

    def get_notebook(self, notebook_id: str) -> JoplinFolder:
        r = requests.get(
            f"{self.base_url}/folders/{notebook_id}", params={"token": self.token}
        )
        r.raise_for_status()
        return JoplinFolder.from_api_response(r)

    def get_subfolder_id(self, title: str) -> Union[str, None]:
        params = {
            "query": title,
            "type": "folder",
            "token": self.token,
        }
        r = requests.get(f"{self.base_url}/search", params=params)
        r.raise_for_status()
        items = r.json()["items"]
        item = [x for x in items if x["parent_id"] == self.notebook_id]
        if len(item) == 0:
            return None
        elif len(item) == 1:
            return item[0]["id"]
        else:
            raise RuntimeError(
                f"More than one subfolder with title {title} found under parent notebook {self.notebook_id}"
            )

    def create_subfolder(self, title: str) -> requests.Response:
        data = {
            "title": title,
            "parent_id": self.notebook_id,
        }
        return requests.post(
            f"{self.base_url}/folders", json=data, params={"token": self.token}
        )

    def config(self, conf: Dict[str, str] = JOPLIN_CONFIG, timeout: int = 20) -> None:
        for k, v in conf.items():
            p = subprocess.run(
                ["joplin", "config", k, v],
                timeout=timeout,
            )
            p.check_returncode()

    def server_is_running(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/ping")
        except requests.ConnectionError:
            return False
        return r.ok

    def _start_server(self) -> None:
        _stdout = subprocess.PIPE
        self.server_process = subprocess.Popen(
            ["joplin", "server", "start"],
            stdout=_stdout,
            stderr=subprocess.STDOUT,
        )

    def start_server(self) -> None:
        self._start_server()
        # wait until server process writes to stdout, which it does when it has started
        line = self.server_process.stdout.readline()
        logger.debug(line)
        sleep(0.5)

    def teardown(self) -> None:
        if self.server_process is not None:
            self.server_process.terminate()

    def sync(self, timeout: int = 20) -> None:
        # TODO better handling of failure (e.g., if nextcloud is not running, or if the ip is misconfigured)
        pattern = re.compile(r"Completed: (\d.*)\(")
        p = subprocess.run(
            ["joplin", "sync"],
            capture_output=True,
            encoding="utf8",
            timeout=timeout,
        )
        success = False
        for line in p.stdout.splitlines():
            m = pattern.search(line)
            if m:
                success = True
                dt_str = m.group(1).strip()
                try:
                    dt = pendulum.parse(dt_str, tz="local")
                    self.last_sync = dt
                except pendulum.parsing.ParserError:
                    pass
        if not success:
            raise RuntimeError("Joplin sync was unsuccessful")

    def post_note(
        self,
        title: str,
        body: str,
        id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> requests.Response:
        if parent_id is None:
            parent_id = self.notebook_id
        data = {
            # "id": day.uid.hex,
            "parent_id": parent_id,
            "title": title,
            "body": body,
        }
        if id is not None:
            data["id"] = id
        return requests.post(
            f"{self.base_url}/notes", json=data, params={"token": self.token}
        )

    def get_note_id_by_title(self, title) -> str:
        params = {
            "token": self.token,
            "query": f'notebook:"{self.parent_notebook.title}" title:"{title}"',
        }
        r = requests.get(f"{self.base_url}/search", params=params)
        items = r.json()["items"]
        if not items:
            return None
        # TODO: fix below (doesn't work for subsubfolders)
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

    def update_note_body(self, note_id: str, new_body: str):
        return requests.put(
            f"{self.base_url}/notes/{note_id}",
            json={"body": new_body},
            params={"token": self.token},
        )

    def create_resource(
        self,
        data: bytes,
        title: str = None,
        ext: str = "jpg",
    ) -> requests.Response:
        hash = hashlib.md5()
        hash.update(data)
        if title is None:
            title = hash.hexdigest()
        if ext and ext.startswith("."):
            ext = ext[1:]
        props = {
            "id": hash.hexdigest(),
            "filename": f"{hash.hexdigest()}.{ext}",
            "title": title,
        }
        response = requests.post(
            f"{self.base_url}/resources",
            files={
                "data": (
                    f"{hash.hexdigest()}.{ext}",
                    data,
                    "multipart/form-data",
                )
            },
            data={"props": json.dumps(props)},
            params={"token": self.token},
        )
        return response

    def reduce_image_size(
        self,
        resource_id: str,
        size: Tuple[int, int] = (512, 512),
        delete_original: bool = False,
    ) -> requests.Response:
        # check to make sure image isn't associated with more than one note
        r = requests.get(
            f"{self.base_url}/resources/{resource_id}/notes",
            params={"token": self.token},
        )
        r_items = r.json().get("items", [])
        if len(r_items) > 1:
            logger.warning(
                f"more than one note is associated with resource {resource_id}:"
            )
            logger.warning(r_items)
            if delete_original is True:
                raise RuntimeError(
                    f"delete_original is set to True, but this resource ({resource_id}) is associated with more than one note"
                )

        resource_file = requests.get(
            f"{self.base_url}/resources/{resource_id}/file",
            params={"token": self.token},
        )
        image_bytes = reduce_image_size(resource_file.content, size)
        r = self.create_resource(data=image_bytes.getvalue())
        if delete_original is True:
            logger.debug(f"deleting original image: {resource_id}")
            self.delete_resource(resource_id, force=True)
        return r

    def delete_resource(
        self, resource_id: str, force: bool = False
    ) -> requests.Response:
        if force is False:
            r = requests.get(
                f"{self.base_url}/resources/{resource_id}/notes",
                params={"token": self.token},
            )
            r_items = r.json().get("items", [])
            if len(r_items) > 0:
                raise RuntimeError(
                    f"Error while deleting resource {resource_id}: resource is associated with one or more notes. Set force=True to delete anyway"
                )
        r = requests.delete(
            f"{self.base_url}/resources/{resource_id}",
            params={"token": self.token},
        )
        return r
