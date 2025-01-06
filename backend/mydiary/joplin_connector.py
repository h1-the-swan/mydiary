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
from typing import Any, Collection, Dict, List, Optional, Tuple, Union, Generator

from .core import get_hash_from_txt, reduce_image_size, reduce_size_recurse
from .models import JoplinNote, JoplinFolder, MyDiaryImage, MyDiaryWords
from .db import engine, Session, select

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())

JOPLIN_BASE_URL = os.environ.get("JOPLIN_BASE_URL") or "http://localhost:41184"
JOPLIN_AUTH_TOKEN = os.environ.get("JOPLIN_AUTH_TOKEN")
JOPLIN_NOTEBOOK_ID = os.environ.get("JOPLIN_NOTEBOOK_ID", None)

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
        self.base_url = JOPLIN_BASE_URL
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
                r_create_subfolder = self.joplin_connector.create_subfolder(title)
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
        try:
            r = requests.get(f"{self.base_url}/ping")
        except requests.ConnectionError:
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
    ) -> str:
        if not parent_notebook_id:
            parent_notebook_id = self.notebook_id
        items = [
            item
            for item in self.yield_notes_by_subfolder_id(parent_notebook_id)
            if item["title"] == title
        ]

        if not items:
            logger.debug(
                f"no note found with title {title} (parent_notebook_id={parent_notebook_id})"
            )
            return "does_not_exist"

        if len(items) > 1:
            raise RuntimeError(f"more than one note found with title {title}")

        return items[0]["id"]

    def get_note_id_by_date(self, dt: datetime) -> str:
        title = title_from_date(dt)
        logger.debug(f"title: {title}")
        subfolder_title = str(dt.year)
        logger.debug(f"subfolder_title: {subfolder_title}")
        subfolder_id = self.get_subfolder_id(subfolder_title)
        logger.debug(f"subfolder_id: {subfolder_id}")
        logger.debug(
            f"getting note id (title={title}, parent_notebook_id={subfolder_id})"
        )
        return self.get_note_id_by_title(title, parent_notebook_id=subfolder_id)

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
        return JoplinNote.from_api_response(r)

    def sync_note_api_to_db_obj(
        self,
        note: Union[str, JoplinNote],
        session: Session,
        commit: bool = True,
        sync_dt: Optional[datetime] = None,
    ):
        if not isinstance(note, JoplinNote):
            note = self.get_note(note)
        if sync_dt is None:
            sync_dt = pendulum.now(tz="UTC")
        md_note = note.md_note
        words_content = md_note.get_section_by_title("words").get_content()
        words_hash = get_hash_from_txt(words_content)
        db_words = session.exec(
            select(MyDiaryWords).where(MyDiaryWords.joplin_note_id == note.id)
        ).one()
        if db_words.hash != words_hash:
            note.words = MyDiaryWords.from_joplin_note(note)
            # session.merge(words_update)
        resource_ids = md_note.get_image_resource_ids()
        note.has_words = len(words_content) > 0
        note.has_images = len(resource_ids) > 0
        note.time_last_api_sync = sync_dt
        session.merge(note)
        if commit is True:
            session.commit()

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

    # def add_image_to_note(
    #     self,
    #     image_bytes: bytes,
    #     size: Tuple[int, int] = (512, 512),
    #     bytes_threshold: int = 60000,
    # ) -> Union[requests.Response, None]:
    #     if len(image_bytes) > bytes_threshold:
    #         image_bytes = reduce_size_recurse(image_bytes, size, bytes_threshold)
    #     r = mydiary_joplin.create_resource(data=image_bytes)
    #     r.raise_for_status()
    #     resource_id = r.json()["id"]
    #     resource_ids.append(f"![](:/{resource_id})")
    #     logger.debug(f"new resource id: {resource_id}")
    #     return r

    def joplin_reduce_image_size(
        self,
        resource_id: str,
        size: Tuple[int, int] = (512, 512),
        bytes_threshold: int = 60000,
        delete_original: bool = False,
    ) -> Union[requests.Response, None]:
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
        image_bytes: bytes = resource_file.content
        if len(image_bytes) > bytes_threshold:
            image_bytes = reduce_size_recurse(image_bytes, size, bytes_threshold)
        else:
            logger.debug(
                f"did not reduce the size of image (resource id: {resource_id} because it was already under the threshold ({bytes_threshold} bytes)"
            )
            return None
        r = self.create_resource(data=image_bytes)
        if delete_original is True:
            logger.debug(f"deleting original image: {resource_id}")
            self.delete_resource(resource_id, force=True)
        return r

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

    def create_thumbnail(
        self,
        image_bytes: bytes,
        name: Optional[str] = None,
        nextcloud_path: Optional[str] = None,
        created_at: Optional[pendulum.DateTime] = None,
    ) -> MyDiaryImage:
        size = (512, 512)
        bytes_threshold = 60000
        if len(image_bytes) > bytes_threshold:
            image_bytes = reduce_size_recurse(image_bytes, size, bytes_threshold)
        r = self.create_resource(data=image_bytes, title=name)
        r.raise_for_status()
        # if failed, need to run self.delete_resource(hash)
        resource_id = r.json()["id"]
        image_hash = hashlib.md5()
        image_hash.update(image_bytes)
        if created_at is None:
            created_at = pendulum.now(tz="UTC")
        mydiary_image = MyDiaryImage(
            hash=image_hash.hexdigest(),
            name=name,
            filepath=None,
            nextcloud_path=nextcloud_path,
            description=None,
            thumbnail_size=len(image_bytes),
            joplin_resource_id=resource_id,
            created_at=created_at.in_timezone("UTC"),
        )
        return mydiary_image

    def get_resource_file(self, resource_id: str) -> bytes:
        r = requests.get(
            f"{self.base_url}/resources/{resource_id}/file",
            params={"token": self.token},
        )
        r.raise_for_status()
        return r.content

    def get_info_all_days(
        self, min_dt=pendulum.parse("2022-01-01"), max_dt=pendulum.today()
    ) -> List[Dict]:
        dt = min_dt
        data = []
        while dt < max_dt:
            note_id = self.get_note_id_by_date(dt)
            if note_id and note_id != "does_not_exist":
                note = self.get_note(note_id)
                words_content = note.md_note.get_section_by_title("words").get_content()
                resource_ids = note.md_note.get_image_resource_ids()
                data.append(
                    {
                        "title": note.title,
                        "note_id": note_id,
                        "has_words": len(words_content) > 0,
                        "has_images": len(resource_ids) > 0,
                    }
                )
            dt = dt.add(days=1)
        return data

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
            resp = r.json()
            for note in resp["items"]:
                yield note
            has_more = resp["has_more"]
            params["page"] += 1

    def yield_all_mydiary_notes(
        self, fields: Optional[List[str]] = None
    ) -> Generator[Dict, None, None]:
        min_year = 2022
        max_year = pendulum.yesterday().year
        for year in range(min_year, max_year + 1):
            subfolder_id = self.get_subfolder_id(str(year))
            for note in self.yield_notes_by_subfolder_id(subfolder_id, fields=fields):
                yield note
