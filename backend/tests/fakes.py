# -*- coding: utf-8 -*-
"""Test doubles that stand in for external services."""

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from mydiary.core import get_hash_from_txt
from mydiary.joplin_connector import MyDiaryJoplin, title_from_date
from mydiary.models import JoplinNote


def make_note(title: str, body: Optional[str], note_id: Optional[str] = None) -> JoplinNote:
    """A JoplinNote as the API would hand it over, titled by date."""
    ts = datetime(2026, 9, 13, 12, 0, 0)
    return JoplinNote(
        id=note_id or f"note-{title}",
        parent_id="folder",
        title=title,
        body=body,
        created_time=ts,
        updated_time=ts,
        body_hash=get_hash_from_txt(body) if body else None,
    )


class FakeJoplin(MyDiaryJoplin):
    """A MyDiaryJoplin that serves notes from memory and never opens a socket.

    Only the read side is implemented: enough for the note sync and the routes
    that fetch a note. Mutate `notes` between calls to simulate edits made in
    the Joplin app."""

    def __init__(
        self, notes: Iterable[JoplinNote], tags: Optional[Dict[str, List[str]]] = None
    ):
        self.notes: List[JoplinNote] = list(notes)
        # Joplin's own note-level tags: note id -> tag titles
        self.note_tags: Dict[str, List[str]] = {k: list(v) for k, v in (tags or {}).items()}
        self.base_url = "http://joplin.invalid"
        self.token = "fake"
        self.notebook_id = "fake-notebook"
        self.server_process = None
        self._parent_notebook = None

    def __enter__(self) -> "FakeJoplin":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _find(self, note_id: str) -> JoplinNote:
        for n in self.notes:
            if n.id == note_id:
                return n
        raise KeyError(note_id)

    def get_note(self, id: str, fields: Optional[List[str]] = None) -> JoplinNote:
        n = self._find(id)
        # a fresh, unattached instance every time, like from_api_response gives
        copy = JoplinNote.model_validate(n.model_dump())
        copy.body_hash = get_hash_from_txt(n.body) if n.body else None
        return copy

    def get_note_id_by_date(self, dt: datetime) -> str:
        title = title_from_date(dt)
        for n in self.notes:
            if n.title == title:
                return n.id
        return "does_not_exist"

    def get_note_tags(self, note_id: str) -> List[str]:
        return list(self.note_tags.get(note_id, []))

    def yield_all_tags(self, fields: Optional[List[str]] = None) -> Iterable[Dict]:
        titles = sorted({t for ts in self.note_tags.values() for t in ts})
        for title in titles:
            yield {"id": f"tag-{title}", "title": title}

    def yield_tag_note_ids(self, tag_id: str) -> Iterable[str]:
        title = tag_id[len("tag-"):]
        for note_id, titles in self.note_tags.items():
            if title in titles:
                yield note_id

    def yield_all_mydiary_notes(self, fields: Optional[List[str]] = None) -> Iterable[Dict]:
        for n in self.notes:
            yield {
                "id": n.id,
                "parent_id": n.parent_id,
                "title": n.title,
                "updated_time": int(n.updated_time.timestamp() * 1000),
            }
