# -*- coding: utf-8 -*-

DESCRIPTION = """Joplin API (local instance)"""

import sys, os, time, json, re
from urllib.parse import urlsplit
import requests
import subprocess
import hashlib
from pathlib import Path
from datetime import date, datetime
from time import sleep
import pendulum
from timeit import default_timer as timer
from typing import Any, Collection, Dict, List, Optional, Tuple, Union, Generator

from .models import (
    JoplinNote,
    JoplinFolder,
)
from .db import engine, Session

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())

JOPLIN_BASE_URL = os.environ.get("JOPLIN_BASE_URL") or "http://localhost"
JOPLIN_AUTH_TOKEN = os.environ.get("JOPLIN_AUTH_TOKEN")
JOPLIN_NOTEBOOK_ID = os.environ.get("JOPLIN_NOTEBOOK_ID", None)

# Joplin's data API claims the first free port in 41184-41194, so a port
# hardcoded in JOPLIN_BASE_URL goes stale whenever something else grabs the
# default 41184 first. If JOPLIN_BASE_URL has no port, scan that range and
# identify the service by its documented ping response. An explicit port in
# JOPLIN_BASE_URL disables the scan.
JOPLIN_PORT_SCAN_RANGE = range(41184, 41195)

_discovered_base_url: Optional[str] = None


def discover_joplin_base_url(force: bool = False) -> str:
    global _discovered_base_url
    if urlsplit(JOPLIN_BASE_URL).port is not None:
        return JOPLIN_BASE_URL.rstrip("/")
    if _discovered_base_url is not None and force is False:
        return _discovered_base_url
    host = JOPLIN_BASE_URL.rstrip("/")
    for port in JOPLIN_PORT_SCAN_RANGE:
        url = f"{host}:{port}"
        try:
            r = requests.get(f"{url}/ping", timeout=1)
        except requests.exceptions.RequestException:
            continue
        if r.ok and r.text.strip() == "JoplinClipperServer":
            logger.info(f"discovered Joplin data API at {url}")
            _discovered_base_url = url
            return url
    logger.warning(
        f"could not find a Joplin data API on {host} ports "
        f"{JOPLIN_PORT_SCAN_RANGE.start}-{JOPLIN_PORT_SCAN_RANGE.stop - 1}; "
        f"falling back to port {JOPLIN_PORT_SCAN_RANGE.start}"
    )
    return f"{host}:{JOPLIN_PORT_SCAN_RANGE.start}"

# for testing purposes. we'll probably want to get this from an environment variable.
# JOPLIN_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"
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
        notebook_id: Optional[str] = None,
        init_config: bool = False,
        # quiet: bool = True,
    ) -> None:
        # ! Don't use more than one level of subnotebooks (i.e., don't use subsubnotebooks). it's hard to work with.
        # subnotebooks are by year (so each will contain 365-366 diary entries)
        self.base_url = discover_joplin_base_url()
        self.token = token
        if not self.token:
            self.token = JOPLIN_AUTH_TOKEN
        self.server_process = server_process
        self.notebook_id = notebook_id
        if not self.notebook_id:
            self.notebook_id = JOPLIN_NOTEBOOK_ID
        # self.quiet = quiet

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
            raise RuntimeError("failed to connect to Joplin server")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is called after the context manager ends
        self.teardown()

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    @property
    def parent_notebook(self) -> JoplinFolder:
        if self._parent_notebook is None:
            self._parent_notebook = self.get_notebook(self.notebook_id)
        return self._parent_notebook

    def get_notebook(self, notebook_id: str) -> JoplinFolder:
        params = {
            "token": self.token,
            "fields": "id,parent_id,title,created_time,updated_time",
        }
        r = requests.get(f"{self.base_url}/folders/{notebook_id}", params=params)
        r.raise_for_status()
        return JoplinFolder.from_api_response(r)

    def get_subfolder_id(
        self, title: str, create_if_not_exists: bool = False
    ) -> Union[str, None]:
        # Example usage: subfolder_id = get_subfolder_id("2024")
        params = {
            "query": title,
            "type": "folder",
            "token": self.token,
        }
        logger.debug(f"getting subfolder id. params: {params}")
        headers = requests.utils.default_headers()
        headers.update({"User-Agent": "My User Agent 1.0"})
        logger.debug(f"headers: {headers}")
        r = requests.get(f"{self.base_url}/search", params=params, headers=headers)
        logger.debug(f"status code is {r.status_code}")
        r.raise_for_status()
        items = r.json()["items"]
        item = [x for x in items if x["parent_id"] == self.notebook_id]
        logger.debug(f"item is {item}")
        if len(item) == 0:
            # subfolder doesn't exist
            if create_if_not_exists is True:
                logger.info(f'"{title}" subfolder (subnotebook) not found.')
                logger.info(f'creating subfolder "{title}"')
                r_create_subfolder = self.create_subfolder(title)
                r_create_subfolder.raise_for_status()
                logger.debug(
                    f"created subfolder. response: {r_create_subfolder.json()}"
                )
                return r_create_subfolder.json()["id"]
            else:
                return None
        elif len(item) == 1:
            return item[0]["id"]
        else:
            raise RuntimeError(
                f"More than one subfolder with title {title} found under parent notebook {self.notebook_id}"
            )

    def create_subfolder(self, title: str, force: bool = False) -> requests.Response:
        if force is False:
            existing_id = self.get_subfolder_id(title)
            if existing_id is not None:
                raise RuntimeError(
                    f"subfolder {title} already exists! subfolder id: {existing_id}"
                )
        data = {
            "title": title,
            "parent_id": self.notebook_id,
        }
        return requests.post(
            f"{self.base_url}/folders", json=data, params={"token": self.token}
        )

    def config(self, conf: Dict[str, str] = JOPLIN_CONFIG, timeout: int = 20) -> None:
        # ! DEPRECATED
        for k, v in conf.items():
            p = subprocess.run(
                ["npx", "joplin", "config", k, v],
                timeout=timeout,
            )
            p.check_returncode()

    def server_is_running(self) -> bool:
        if self._ping():
            return True
        # Joplin may have restarted on a different port; rescan once
        if urlsplit(JOPLIN_BASE_URL).port is None:
            self.base_url = discover_joplin_base_url(force=True)
            return self._ping()
        return False

    def _ping(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/ping", timeout=5)
        except requests.exceptions.RequestException:
            return False
        return r.ok

    def _start_server(self) -> None:
        # ! DEPRECATED
        _stdout = subprocess.PIPE
        self.server_process = subprocess.Popen(
            ["npx", "joplin", "server", "start"],
            stdout=_stdout,
            stderr=subprocess.STDOUT,
        )

    def start_server(self) -> None:
        # ! DEPRECATED
        self._start_server()
        # wait until server process writes to stdout, which it does when it has started
        line = self.server_process.stdout.readline()
        logger.debug(line)
        sleep(0.5)

    def teardown(self) -> None:
        # ! DEPRECATED
        if self.server_process is not None:
            self.server_process.terminate()

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

    def get_note_id_by_title(
        self, title, parent_notebook_id: Optional[str] = None
    ) -> Optional[str]:
        if not parent_notebook_id:
            parent_notebook_id = self.notebook_id
        # a conflict copy Joplin set aside keeps the original's folder and
        # title, so it would otherwise look like a second note for the day
        items = [
            item
            for item in self.yield_notes_by_subfolder_id(
                parent_notebook_id, fields=["id", "title", "is_conflict"]
            )
            if item["title"] == title and not item.get("is_conflict")
        ]

        if not items:
            logger.debug(
                f"no note found with title {title} (parent_notebook_id={parent_notebook_id})"
            )
            return None

        if len(items) > 1:
            raise RuntimeError(f"more than one note found with title {title}")

        return items[0]["id"]

    def get_note(self, id: str, fields: Optional[List[str]] = None) -> JoplinNote:
        if fields is None:
            # default list of fields to fetch
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
        r.raise_for_status()
        return JoplinNote.from_api_response(r)

    def _yield_pages(self, url: str, fields: List[str]) -> Generator[Dict, None, None]:
        params = {
            "token": self.token,
            "fields": ",".join(fields),
            "limit": 100,
            "page": 1,
        }
        while True:
            r = requests.get(url, params=params)
            r.raise_for_status()
            resp = r.json()
            yield from resp["items"]
            if not resp.get("has_more"):
                return
            params["page"] += 1

    def get_note_tags(self, note_id: str) -> List[str]:
        """Titles of Joplin's own tags on a note."""
        return [
            item["title"]
            for item in self._yield_pages(f"{self.base_url}/notes/{note_id}/tags", ["id", "title"])
        ]

    def yield_all_tags(self, fields: Optional[List[str]] = None) -> Generator[Dict, None, None]:
        yield from self._yield_pages(f"{self.base_url}/tags", fields or ["id", "title"])

    def yield_tag_note_ids(self, tag_id: str) -> Generator[str, None, None]:
        for item in self._yield_pages(f"{self.base_url}/tags/{tag_id}/notes", ["id"]):
            yield item["id"]

    def update_note_body(self, note_id: str, new_body: str):
        return requests.put(
            f"{self.base_url}/notes/{note_id}",
            json={"body": new_body},
            params={"token": self.token},
        )

    def resource_exists(self, resource_id: str) -> bool:
        r = requests.get(
            f"{self.base_url}/resources/{resource_id}",
            params={"token": self.token},
        )
        return r.status_code == 200

    def get_resource_size(self, resource_id: str) -> Optional[int]:
        """Bytes stored for a resource, without downloading the file itself."""
        r = requests.get(
            f"{self.base_url}/resources/{resource_id}",
            params={"token": self.token, "fields": "size"},
        )
        if r.status_code != 200:
            return None
        return r.json().get("size")

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
        print(hash.hexdigest())
        props = {
            "id": hash.hexdigest(),
            "filename": f"{hash.hexdigest()}.{ext}",
            "title": title,
        }
        logger.debug(f"creating resource. id: {props['id']} | title: {props['title']}")
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

    def delete_resource(
        self,
        resource_id: str,
        force: bool = False,
        ignore_id: Optional[Union[str, Collection[str]]] = None,
    ) -> requests.Response:
        if ignore_id is None:
            ignore_id = set()
        elif isinstance(ignore_id, str):
            ignore_id = [ignore_id]
        ignore_id = set(ignore_id)

        if force is False:
            r = requests.get(
                f"{self.base_url}/resources/{resource_id}/notes",
                params={"token": self.token},
            )
            r_items = r.json().get("items", [])
            if (
                len(r_items) > 0
                and set(item.get("id") for item in r_items) != ignore_id
            ):
                raise RuntimeError(
                    f"Error while deleting resource {resource_id}: resource is associated with one or more notes. Set force=True to delete anyway"
                )
        r = requests.delete(
            f"{self.base_url}/resources/{resource_id}",
            params={"token": self.token},
        )
        return r

    def get_resource_file(self, resource_id: str) -> bytes:
        r = requests.get(
            f"{self.base_url}/resources/{resource_id}/file",
            params={"token": self.token},
        )
        r.raise_for_status()
        return r.content

    def yield_notes_by_subfolder_id(
        self,
        subfolder_id: str,
        fields: Optional[List[str]] = None,
    ) -> Generator[Dict, None, None]:
        has_more = True
        url = f"{self.base_url}/folders/{subfolder_id}/notes"
        if fields is None:
            fields = [
                "id",
                "parent_id",
                "title",
                "created_time",
                "updated_time",
            ]
        params = {
            "token": self.token,
            "fields": fields,
            "limit": 100,
            "page": 1,
            "order_by": "updated_time",
            "order_dir": "DESC",
        }
        while has_more:
            r = requests.get(url, params=params)
            r.raise_for_status()
            resp = r.json()
            for note in resp["items"]:
                yield note
            has_more = resp["has_more"]
            params["page"] += 1
