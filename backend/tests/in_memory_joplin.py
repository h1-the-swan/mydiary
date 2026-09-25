# -*- coding: utf-8 -*-
"""An in-memory Joplin that implements the whole JoplinPort."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterator, List, Optional, Tuple

from mydiary.core import get_hash_from_txt
from mydiary.joplin_connector import title_from_date
from mydiary.joplin_port import JoplinError
from mydiary.models import JoplinNote


@dataclass
class StoredFolder:
    id: str
    title: str
    parent_id: str


@dataclass
class StoredNote:
    id: str
    parent_id: str
    title: str
    body: str
    created_time: datetime
    updated_time: datetime


@dataclass
class StoredResource:
    data: bytes
    title: str
    ext: str


def _new_id() -> str:
    return uuid.uuid4().hex


class InMemoryJoplin:
    """A Joplin notebook held in memory, filed by year like the real diary.

    It shares no code with `MyDiaryJoplin` on purpose: a method missing here
    fails with AttributeError instead of falling through to real HTTP.

    Beyond the port, tests get direct access to `folders`, `notes`,
    `resources` and `updates` (every body the app PUT, in order), plus a few
    controls: `add_note` and `tag_note` to seed, `clobber_next_update` to
    stand in for the Joplin app's autosave writing back a stale copy, and
    `fail_next_update`."""

    def __init__(self, notebook_id: str = "0" * 32) -> None:
        self.notebook_id = notebook_id
        self.folders: Dict[str, StoredFolder] = {}
        self.notes: Dict[str, StoredNote] = {}
        self.resources: Dict[str, StoredResource] = {}
        self.tags: Dict[str, str] = {}  # tag id -> title
        self.note_tag_ids: Dict[str, List[str]] = {}  # note id -> tag ids
        self.updates: List[Tuple[str, str]] = []
        self._clobbers: Dict[str, str] = {}
        self._fail_next_update = False
        # Joplin's times are naive local datetimes; a fixed clock that moves
        # on every write keeps "updated since" comparisons deterministic
        self._clock = datetime(2026, 1, 1, 12, 0, 0)

    def _tick(self) -> datetime:
        self._clock += timedelta(minutes=1)
        return self._clock

    def _stored_note(self, note_id: str) -> StoredNote:
        try:
            return self.notes[note_id]
        except KeyError:
            raise JoplinError(f"no note {note_id}") from None

    # --- notes ---

    def get_note_id_by_date(self, dt: date) -> Optional[str]:
        folder_id = self._year_folder_id(dt.year)
        if folder_id is None:
            return None
        title = title_from_date(dt)
        ids = [
            n.id
            for n in self.notes.values()
            if n.parent_id == folder_id and n.title == title
        ]
        if len(ids) > 1:
            raise RuntimeError(f"more than one note found with title {title}")
        return ids[0] if ids else None

    def get_note(self, note_id: str) -> JoplinNote:
        n = self._stored_note(note_id)
        return JoplinNote(
            id=n.id,
            parent_id=n.parent_id,
            title=n.title,
            body=n.body,
            created_time=n.created_time,
            updated_time=n.updated_time,
            body_hash=get_hash_from_txt(n.body) if n.body else None,
        )

    def create_note(self, title: str, body: str, folder_id: str) -> str:
        # like Joplin, this doesn't check that the folder exists
        now = self._tick()
        note_id = _new_id()
        self.notes[note_id] = StoredNote(
            id=note_id,
            parent_id=folder_id,
            title=title,
            body=body,
            created_time=now,
            updated_time=now,
        )
        return note_id

    def update_note_body(self, note_id: str, body: str) -> None:
        if self._fail_next_update:
            self._fail_next_update = False
            raise JoplinError(f"updating note {note_id}: simulated failure")
        n = self._stored_note(note_id)
        n.body = body
        n.updated_time = self._tick()
        self.updates.append((note_id, body))
        if note_id in self._clobbers:
            n.body = self._clobbers.pop(note_id)
            n.updated_time = self._tick()

    # --- resources ---

    def create_resource(
        self, data: bytes, title: Optional[str] = None, ext: str = "jpg"
    ) -> str:
        resource_id = hashlib.md5(data).hexdigest()
        if resource_id in self.resources:
            raise JoplinError(f"resource {resource_id} already exists")
        if ext and ext.startswith("."):
            ext = ext[1:]
        self.resources[resource_id] = StoredResource(
            data=data, title=resource_id if title is None else title, ext=ext
        )
        return resource_id

    def delete_resource(self, resource_id: str) -> None:
        if self.resources.pop(resource_id, None) is None:
            raise JoplinError(f"no resource {resource_id}")

    def resource_exists(self, resource_id: str) -> bool:
        return resource_id in self.resources

    # --- tags ---

    def get_note_tags(self, note_id: str) -> List[str]:
        # Joplin answers 200 with no tags for a note it doesn't have
        return [self.tags[t] for t in self.note_tag_ids.get(note_id, [])]

    def yield_all_tags(self) -> Iterator[Dict[str, str]]:
        for tag_id, title in self.tags.items():
            yield {"id": tag_id, "title": title}

    def yield_tag_note_ids(self, tag_id: str) -> Iterator[str]:
        if tag_id not in self.tags:
            raise JoplinError(f"no tag {tag_id}")
        for note_id, tag_ids in self.note_tag_ids.items():
            if tag_id in tag_ids:
                yield note_id

    # --- folders ---

    def _year_folder_id(self, year: int) -> Optional[str]:
        ids = [
            f.id
            for f in self.folders.values()
            if f.parent_id == self.notebook_id and f.title == str(year)
        ]
        if len(ids) > 1:
            raise RuntimeError(f"More than one subfolder with title {year}")
        return ids[0] if ids else None

    def get_or_create_year_folder(self, year: int) -> str:
        folder_id = self._year_folder_id(year)
        if folder_id is None:
            folder_id = _new_id()
            self.folders[folder_id] = StoredFolder(
                id=folder_id, title=str(year), parent_id=self.notebook_id
            )
        return folder_id

    # --- test controls ---

    def add_note(self, title: str, body: str) -> str:
        """Seed a Diary Note titled `YYYY-MM-DD`, filed in its year's folder."""
        folder_id = self.get_or_create_year_folder(int(title[:4]))
        return self.create_note(title, body, folder_id)

    def tag_note(self, note_id: str, title: str) -> None:
        """Put one of Joplin's own tags on a note, creating the tag if needed."""
        self._stored_note(note_id)
        tag_id = next((i for i, t in self.tags.items() if t == title), None)
        if tag_id is None:
            tag_id = _new_id()
            self.tags[tag_id] = title
        tag_ids = self.note_tag_ids.setdefault(note_id, [])
        if tag_id not in tag_ids:
            tag_ids.append(tag_id)

    def clobber_next_update(self, note_id: str, body: str) -> None:
        """After the next body update to this note lands, overwrite it with
        `body`, the way the Joplin app's autosave writes back a stale copy."""
        self._clobbers[note_id] = body

    def fail_next_update(self) -> None:
        """Make the next body update raise JoplinError and change nothing."""
        self._fail_next_update = True
