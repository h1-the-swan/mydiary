# -*- coding: utf-8 -*-
"""The Diary Note: one Joplin note per Diary Day, and its Note Mirror.

This module finds a Diary Note by date and refreshes the Note Mirror, the
database's copy of the note and everything derived from it (words, which
Photos it shows, tags). Joplin holds the authoritative note; the mirror is
always refreshed from what Joplin returned, never the other way round. See
CONTEXT.md for the terms.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pendulum
from sqlalchemy import update
from sqlmodel import Session, select

from .core import get_hash_from_txt
from .joplin_port import JoplinPort
from .markdown_edits import MarkdownDoc
from .models import JoplinNote, JoplinNoteImageLink, MyDiaryImage, MyDiaryWords

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

# the first year the diary has notes for; the hourly sync lists from here
FIRST_DIARY_YEAR = 2022


class WordsConflict(Exception):
    """Refreshing the mirror would lose or overwrite words only the database has.

    The Note Mirror's words are meant to equal the Words section of the note
    last mirrored. When they don't, or when the note's Words section has gone
    empty while the database still has words, the refresh stops and leaves
    the database alone for someone to look at."""

    def __init__(self, title: str, reason: str) -> None:
        super().__init__(f"{title}: {reason}")
        self.title = title
        self.reason = reason


@dataclass
class NoteSyncSummary:
    """What a note sync did. `notes_checked` counts listings, not fetches."""

    notes_checked: int = 0
    notes_synced: int = 0
    tags_added: int = 0
    tags_removed: int = 0


@dataclass
class DiaryNote:
    """A Diary Note that exists in Joplin."""

    joplin: JoplinPort
    id: str
    date: date

    @classmethod
    def find(cls, joplin: JoplinPort, dt: date) -> Optional["DiaryNote"]:
        """The Diary Note for a date, or None if Joplin has none."""
        if isinstance(dt, datetime):
            dt = dt.date()
        note_id = joplin.get_note_id_by_date(dt)
        if note_id is None:
            return None
        return cls(joplin=joplin, id=note_id, date=dt)

    def read(self) -> JoplinNote:
        return self.joplin.get_note(self.id)

    def refresh_mirror(self, session: Session, commit: bool = True) -> Tuple[int, int]:
        """Read the note and refresh its mirror. Returns the tag (added,
        removed) counts."""
        return refresh_note_mirror(session, self.joplin, self.read(), commit=commit)


def words_of(body: Optional[str]) -> str:
    """The content of a body's Words section, or "" if it has none."""
    if not body:
        return ""
    try:
        return MarkdownDoc(body).get_section_by_title("words").get_content()
    except KeyError:
        return ""


def image_resource_ids_of(body: Optional[str]) -> List[str]:
    """The resource ids referenced in a body's Images section, in order."""
    if not body:
        return []
    try:
        return MarkdownDoc(body).get_image_resource_ids()
    except KeyError:
        return []


def refresh_note_mirror(
    session: Session,
    joplin: JoplinPort,
    note: JoplinNote,
    sync_dt: Optional[datetime] = None,
    commit: bool = True,
) -> Tuple[int, int]:
    """Refresh the Note Mirror from a note as Joplin just returned it.

    Always full: the JoplinNote row (body, hash, flags, sync time), the
    MyDiaryWords row, the image links rebuilt from the Images section, the
    hashtag links from the body and Joplin's own tags on the note (one more
    request). A note re-created in Joplin under a new id takes over the old
    row. Raises `WordsConflict`, having changed nothing, when the refresh
    would lose words only the database has. Returns the tag (added, removed)
    counts."""
    from .tags import sync_joplin_note_tags, sync_note_tags

    if sync_dt is None:
        sync_dt = pendulum.now(tz="UTC")
    words = words_of(note.body)
    resource_ids = image_resource_ids_of(note.body)

    mirrored = session.get(JoplinNote, note.id)
    stale = None
    if mirrored is None:
        stale = session.exec(
            select(JoplinNote).where(JoplinNote.title == note.title)
        ).one_or_none()
    owner = mirrored or stale
    db_words = None
    if owner is not None:
        db_words = session.exec(
            select(MyDiaryWords).where(MyDiaryWords.joplin_note_id == owner.id)
        ).one_or_none()
    _check_words(
        note,
        words,
        previous_body=mirrored.body if mirrored is not None else None,
        db_words=db_words,
    )

    if stale is not None:
        _rekey_recreated_note(session, stale, note.id)

    if words:
        words_hash = get_hash_from_txt(words)
        if db_words is None:
            session.add(MyDiaryWords.from_joplin_note(note))
        elif db_words.hash != words_hash:
            # in place: assigning a fresh row to note.words would leave the
            # old one behind with a NULL note id (no delete-orphan cascade)
            db_words.txt = words
            db_words.hash = words_hash
            db_words.updated_at = note.updated_time
            db_words.note_title = note.title
            session.add(db_words)

    note.has_words = len(words) > 0
    note.has_images = len(resource_ids) > 0
    note.time_last_api_sync = sync_dt
    session.merge(note)
    session.flush()
    _rebuild_image_links(session, note, resource_ids)
    added, removed = sync_note_tags(session, note, commit=False)
    j_added, j_removed = sync_joplin_note_tags(
        session, note.title, joplin.get_note_tags(note.id), commit=False
    )
    if commit is True:
        session.commit()
    return added + j_added, removed + j_removed


def _check_words(
    note: JoplinNote,
    words: str,
    previous_body: Optional[str],
    db_words: Optional[MyDiaryWords],
) -> None:
    # a missing row counts as "": the mirror only creates one once a note
    # has words
    stored = db_words.txt if db_words is not None else ""
    # with no previously mirrored body (first sight of a note, or one
    # re-created under a new id) there is nothing to hold the row to
    if previous_body is not None and stored != words_of(previous_body):
        raise WordsConflict(
            note.title,
            "the database's words differ from the Words of the note last "
            "mirrored, so something other than the mirror wrote them",
        )
    if stored and not words:
        raise WordsConflict(
            note.title,
            "the note's Words section is empty or missing but the database "
            "has words; the database may hold the only copy",
        )


def _rekey_recreated_note(session: Session, stale: JoplinNote, new_id: str) -> None:
    """Move a mirrored note onto a new Joplin id.

    A note deleted and re-created in the Joplin app keeps its date title but
    gets a new id, and titles are unique in the mirror. Rather than fail the
    insert, the old row and everything keyed on it (words, image links) are
    moved to the new id. Tag links are keyed by title, so they need nothing."""
    old_id = stale.id
    logger.warning(
        f"note {stale.title!r} was re-created in Joplin: {old_id} -> {new_id}"
    )
    session.expunge(stale)
    for model in (MyDiaryWords, JoplinNoteImageLink):
        session.execute(
            update(model)
            .where(model.joplin_note_id == old_id)
            .values(joplin_note_id=new_id)
        )
    session.execute(update(JoplinNote).where(JoplinNote.id == old_id).values(id=new_id))
    session.flush()


def _rebuild_image_links(
    session: Session, note: JoplinNote, resource_ids: List[str]
) -> None:
    """Make the note's image links follow its Images section, in order.

    Refs with no MyDiaryImage row (legacy Google Photos ids) are skipped. A
    ref repeated in the section is linked once, at its first position."""
    wanted: List[int] = []
    for resource_id in dict.fromkeys(resource_ids):
        image = session.exec(
            select(MyDiaryImage).where(MyDiaryImage.joplin_resource_id == resource_id)
        ).first()
        if image is not None:
            wanted.append(image.id)
    links = session.exec(
        select(JoplinNoteImageLink)
        .where(JoplinNoteImageLink.joplin_note_id == note.id)
        .order_by(JoplinNoteImageLink.sequence_num)
    ).all()
    have = [(link.mydiary_image_id, link.sequence_num) for link in links]
    if have == [(image_id, i) for i, image_id in enumerate(wanted, start=1)]:
        return
    for link in links:
        session.delete(link)
    session.flush()
    for i, image_id in enumerate(wanted, start=1):
        session.add(
            JoplinNoteImageLink(
                joplin_note_id=note.id,
                mydiary_image_id=image_id,
                sequence_num=i,
                note_title=note.title,
            )
        )
    session.flush()


def sync_one_day(session: Session, joplin: JoplinPort, dt: date) -> NoteSyncSummary:
    """Mirror the one Diary Note for a day, if it exists."""
    summary = NoteSyncSummary()
    diary_note = DiaryNote.find(joplin, dt)
    if diary_note is None:
        return summary
    summary.notes_checked = 1
    added, removed = diary_note.refresh_mirror(session)
    summary.notes_synced = 1
    summary.tags_added = added
    summary.tags_removed = removed
    return summary


def sync_joplin_tags(session: Session, joplin: JoplinPort) -> Tuple[int, int]:
    """Reconcile every diary day's joplin-sourced links with Joplin.

    Tagging a note in Joplin does not change the note's updated_time, so the
    per-note "fetch what changed" rule cannot see it. This reads from the tag
    side instead: one listing of all tags, then one request per tag for its
    notes. Notes outside the mirror (other notebooks, or not yet fetched) are
    ignored."""
    from .tags import sync_joplin_tags_bulk

    title_by_note_id = dict(session.exec(select(JoplinNote.id, JoplinNote.title)).all())
    titles_by_day = {}
    for tag in joplin.yield_all_tags():
        for note_id in joplin.yield_tag_note_ids(tag["id"]):
            day = title_by_note_id.get(note_id)
            if day is not None:
                titles_by_day.setdefault(day, []).append(tag["title"])
    return sync_joplin_tags_bulk(session, titles_by_day)


def sync_changed_notes(
    session: Session, joplin: JoplinPort, force: bool = False
) -> NoteSyncSummary:
    """Mirror every Diary Note whose Joplin copy is newer than the mirror.

    The listing is cheap (no bodies). A body is fetched only for a note that
    is new, edited (updated_time newer, with a second's slack because both
    sides are naive local datetimes), was never given a body, or was never
    synced. `force` fetches all of them. A note that fails to sync, including
    one with a `WordsConflict`, is logged and skipped, not fatal."""
    summary = NoteSyncSummary()
    known = {
        note_id: (updated_time, body_is_null, sync_is_null)
        for note_id, updated_time, body_is_null, sync_is_null in session.exec(
            select(
                JoplinNote.id,
                JoplinNote.updated_time,
                JoplinNote.body.is_(None),
                JoplinNote.time_last_api_sync.is_(None),
            )
        ).all()
    }
    for year in range(FIRST_DIARY_YEAR, pendulum.yesterday().year + 1):
        for item in joplin.yield_year_notes(year):
            summary.notes_checked += 1
            row = known.get(item.id)
            needs_fetch = (
                force
                or row is None
                or row[1]
                or row[2]
                or item.updated_time > row[0] + timedelta(seconds=1)
            )
            if not needs_fetch:
                continue
            try:
                added, removed = refresh_note_mirror(
                    session, joplin, joplin.get_note(item.id)
                )
            except WordsConflict as e:
                logger.error(f"words conflict on {e.title}, not synced: {e.reason}")
                session.rollback()
                continue
            except Exception:
                logger.exception(f"failed to sync note {item.id} ({item.title})")
                session.rollback()
                continue
            summary.notes_synced += 1
            summary.tags_added += added
            summary.tags_removed += removed
    try:
        added, removed = sync_joplin_tags(session, joplin)
    except Exception:
        logger.exception("failed to sync Joplin's note tags")
        session.rollback()
    else:
        summary.tags_added += added
        summary.tags_removed += removed
    return summary
