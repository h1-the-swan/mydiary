# -*- coding: utf-8 -*-
"""The narrow port the app uses to talk to Joplin, and its HTTP adapter.

`JoplinPort` covers only what talks to Joplin: finding, reading, creating and
updating notes, creating and deleting resources, reading tags, and the year
subfolders notes are filed in. `HttpJoplin` implements it over the Joplin data
API. Tests use `InMemoryJoplin` (tests/in_memory_joplin.py), which implements
the same port without any HTTP.

A missing note is `None` here. The `"does_not_exist"` sentinel the client still
returns stops at this boundary.
"""

from contextlib import contextmanager
from datetime import date
from typing import Dict, Iterator, List, Optional, Protocol, runtime_checkable

import requests

from .joplin_connector import MyDiaryJoplin, title_from_date
from .models import JoplinNote


class JoplinError(Exception):
    """A Joplin request failed, or named a note or resource Joplin doesn't have."""


@runtime_checkable
class JoplinPort(Protocol):
    def get_note_id_by_date(self, dt: date) -> Optional[str]:
        """The id of the Diary Note titled `YYYY-MM-DD` in the year's subfolder."""
        ...

    def get_note(self, note_id: str) -> JoplinNote:
        """The whole note, body included, as a fresh unattached instance."""
        ...

    def create_note(self, title: str, body: str, folder_id: str) -> str:
        """Create a note in a folder and return its id."""
        ...

    def update_note_body(self, note_id: str, body: str) -> None: ...

    def create_resource(
        self, data: bytes, title: Optional[str] = None, ext: str = "jpg"
    ) -> str:
        """Store a file and return its id, the md5 of `data`.

        The id is derived from the content, so storing bytes that are already
        stored raises. Check `resource_exists` first to reuse one."""
        ...

    def delete_resource(self, resource_id: str) -> None: ...

    def resource_exists(self, resource_id: str) -> bool: ...

    def get_note_tags(self, note_id: str) -> List[str]:
        """Titles of Joplin's own tags on a note."""
        ...

    def yield_all_tags(self) -> Iterator[Dict[str, str]]:
        """Every tag, as `{"id": ..., "title": ...}`."""
        ...

    def yield_tag_note_ids(self, tag_id: str) -> Iterator[str]: ...

    def get_or_create_year_folder(self, year: int) -> str:
        """The id of the notebook's subfolder for a year, created if missing."""
        ...


@contextmanager
def _joplin_errors(what: str) -> Iterator[None]:
    try:
        yield
    except requests.RequestException as e:
        raise JoplinError(f"{what}: {e}") from e


class HttpJoplin:
    """`JoplinPort` over the Joplin data API.

    For now this wraps `MyDiaryJoplin` rather than being it. Four of the
    port's names (`get_note_id_by_date`, `update_note_body`, `create_resource`,
    `delete_resource`) are taken on the client by methods whose return values
    (the sentinel, a `requests.Response`) existing callers still read. Once
    those callers use the port, this can fold into the client."""

    def __init__(self, client: MyDiaryJoplin) -> None:
        self.client = client

    def get_note_id_by_date(self, dt: date) -> Optional[str]:
        # the year's folder only: the client's own lookup falls back to the
        # notebook root when the folder is missing
        with _joplin_errors(f"finding the note for {dt}"):
            folder_id = self.client.get_subfolder_id(str(dt.year))
            if folder_id is None:
                return None
            note_id = self.client.get_note_id_by_title(
                title_from_date(dt), parent_notebook_id=folder_id
            )
        if note_id == "does_not_exist":
            return None
        return note_id

    def get_note(self, note_id: str) -> JoplinNote:
        with _joplin_errors(f"getting note {note_id}"):
            return self.client.get_note(note_id)

    def create_note(self, title: str, body: str, folder_id: str) -> str:
        with _joplin_errors(f"creating note {title}"):
            r = self.client.post_note(title=title, body=body, parent_id=folder_id)
            r.raise_for_status()
        return r.json()["id"]

    def update_note_body(self, note_id: str, body: str) -> None:
        with _joplin_errors(f"updating note {note_id}"):
            self.client.update_note_body(note_id, body).raise_for_status()

    def create_resource(
        self, data: bytes, title: Optional[str] = None, ext: str = "jpg"
    ) -> str:
        with _joplin_errors("creating a resource"):
            r = self.client.create_resource(data=data, title=title, ext=ext)
            r.raise_for_status()
        return r.json()["id"]

    def delete_resource(self, resource_id: str) -> None:
        with _joplin_errors(f"deleting resource {resource_id}"):
            self.client.delete_resource(resource_id, force=True).raise_for_status()

    def resource_exists(self, resource_id: str) -> bool:
        with _joplin_errors(f"looking up resource {resource_id}"):
            return self.client.resource_exists(resource_id)

    def get_note_tags(self, note_id: str) -> List[str]:
        with _joplin_errors(f"getting the tags of note {note_id}"):
            return self.client.get_note_tags(note_id)

    def yield_all_tags(self) -> Iterator[Dict[str, str]]:
        with _joplin_errors("listing tags"):
            yield from self.client.yield_all_tags()

    def yield_tag_note_ids(self, tag_id: str) -> Iterator[str]:
        with _joplin_errors(f"listing the notes of tag {tag_id}"):
            yield from self.client.yield_tag_note_ids(tag_id)

    def get_or_create_year_folder(self, year: int) -> str:
        with _joplin_errors(f"finding the {year} folder"):
            return self.client.get_subfolder_id(str(year), create_if_not_exists=True)
