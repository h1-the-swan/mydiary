# -*- coding: utf-8 -*-
"""A Refresh of a Diary Note's Google Calendar events section, with a Refresh
Preview the diarist approves first (see CONTEXT.md and ADR-0002).

The preview reads only: Google, and the note. Applying it writes exactly the
`after` the diarist saw, or nothing, raising `GcalSectionChanged` if either
the calendar or the note's section has moved on since the preview."""

import difflib
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional, Protocol

from .db import Session
from .diary_note import DiaryNote, _find_section, _has_open_fence
from .joplin_port import JoplinPort
from .markdown_edits import MarkdownDoc
from .models import GoogleCalendarEvent
from .mydiary_day import google_calendar_events_markdown

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

SECTION = "Google Calendar events"


class CalendarSource(Protocol):
    """What a Refresh needs from Google Calendar (`MyDiaryGCal`)."""

    def get_events_for_day(self, dt: datetime) -> List[GoogleCalendarEvent]: ...

    def save_events_to_database(
        self, events: List[GoogleCalendarEvent], session: Optional[Session] = None
    ) -> None: ...


class NoDiaryNote(LookupError):
    """The day has no Diary Note to refresh."""


class SectionUnreadable(Exception):
    """The note's Google Calendar events section can't be told apart (the
    heading twice, or an unclosed ``` fence), so a Refresh can't write it."""


class GcalSectionChanged(Exception):
    """The calendar or the note's section changed since the preview, so
    nothing was written. `side` is "calendar" or "note"."""

    def __init__(self, side: Literal["calendar", "note"]) -> None:
        self.side = side
        super().__init__(f"the {side} changed since the preview")


@dataclass
class DiffLine:
    op: Literal["same", "add", "remove"]
    text: str


@dataclass
class GcalRefreshPreview:
    before: str  # the section as the note has it ("" if it has none)
    after: str  # the section as a Refresh would write it
    diff: List[DiffLine] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.before != self.after


def line_diff(before: str, after: str) -> List[DiffLine]:
    """`before` to `after` line by line, a changed line shown as its removal
    followed by its addition."""
    # split as MarkdownDoc does, so the diff shows the lines that get written
    old = before.split("\n") if before else []
    new = after.split("\n") if after else []
    lines: List[DiffLine] = []
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            lines.extend(DiffLine("same", t) for t in old[i1:i2])
            continue
        lines.extend(DiffLine("remove", t) for t in old[i1:i2])
        lines.extend(DiffLine("add", t) for t in new[j1:j2])
    return lines


def _render(events: List[GoogleCalendarEvent]) -> str:
    # stripped as `NoteEdit.set_section` strips it, so `after` is what lands
    # in the note (an event title ending in a space, say)
    return google_calendar_events_markdown(events).strip()


def _section(body: Optional[str]) -> str:
    """The note's Google Calendar events section ("" if it has none), read as
    `NoteEdit` would find it to write. `SectionUnreadable` if it can't."""
    body = (body or "").replace("\r\n", "\n")
    if _has_open_fence(body):
        raise SectionUnreadable("the note has an unclosed ``` fence")
    try:
        section = _find_section(MarkdownDoc(body), SECTION)
    except ValueError as e:
        raise SectionUnreadable(str(e)) from e
    return section.get_content() if section is not None else ""


def _find(joplin: JoplinPort, dt: datetime) -> DiaryNote:
    diary_note = DiaryNote.find(joplin, dt)
    if diary_note is None:
        raise NoDiaryNote(f"no Diary Note for {dt.date()}")
    return diary_note


def preview_gcal_refresh(
    joplin: JoplinPort, dt: datetime, gcal: CalendarSource
) -> GcalRefreshPreview:
    """What a Refresh of the day's Google Calendar events section would
    write. Writes nothing anywhere."""
    diary_note = _find(joplin, dt)
    after = _render(gcal.get_events_for_day(dt))
    before = _section(diary_note.read().body)
    return GcalRefreshPreview(before=before, after=after, diff=line_diff(before, after))


def apply_gcal_refresh(
    session: Session,
    joplin: JoplinPort,
    dt: datetime,
    before: str,
    after: str,
    gcal: CalendarSource,
) -> bool:
    """Write `after` as the day's Google Calendar events section, if the
    calendar still renders to `after` and the note's section is still
    `before`; otherwise raise `GcalSectionChanged` and write nothing. The
    day's events are saved to the database only once the note is written.
    Returns whether the note was written (False when it already held
    `after`). If saving the events fails, the note has already been
    written."""
    diary_note = _find(joplin, dt)
    events = gcal.get_events_for_day(dt)
    if _render(events) != after:
        raise GcalSectionChanged("calendar")
    with diary_note.edit(session) as edit:
        if _section(edit.note.body) != before:
            raise GcalSectionChanged("note")
        edit.set_section(SECTION, after)
    # after the edit: it commits the session itself, and asks callers not to
    # hold pending writes across it
    gcal.save_events_to_database(events, session=session)
    logger.info(f"refreshed Google Calendar events for {dt.date()}: wrote={edit.wrote}")
    return edit.wrote
