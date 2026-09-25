# -*- coding: utf-8 -*-
"""The Diary Note: one Joplin note per Diary Day, and its Note Mirror.

This module holds the section registry, finds and creates Diary Notes by
date, owns every later write to one (`DiaryNote.edit()`, which only writes
App-owned Sections; see ADR-0002), and
refreshes the Note Mirror, the database's copy of the note and everything
derived from it (words, which Photos it shows, tags). Joplin holds the
authoritative note; the mirror is always refreshed from what Joplin returned,
never the other way round. See CONTEXT.md for the terms.
"""

import hashlib
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, Generator, List, Optional, Tuple

import pendulum
from sqlalchemy import update
from sqlmodel import Session, select

from .core import get_hash_from_txt
from .joplin_connector import title_from_date
from .joplin_port import JoplinPort
from .markdown_edits import MarkdownDoc, MarkdownSection
from .models import JoplinNote, JoplinNoteImageLink, MyDiaryImage, MyDiaryWords

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

# the first year the diary has notes for; the hourly sync lists from here
FIRST_DIARY_YEAR = 2022

# inside DiaryNote's body, `date` is the field, not the type
_Date = date


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


class NoteClobbered(Exception):
    """A write to a Diary Note didn't stick.

    After writing, and once more after rewriting, Joplin still held a body
    without this edit's sections: usually the Joplin app's autosave writing
    back a stale copy of the note it has open."""

    def __init__(self, title: str, headings: List[str]) -> None:
        super().__init__(
            f"{title}: Joplin kept overwriting the {', '.join(headings)} "
            "section(s); is the note open in the Joplin app?"
        )
        self.title = title
        self.headings = headings


class SectionNotAppOwned(ValueError):
    """Only App-owned Sections may be written once a note exists (ADR-0002)."""


class NoteExists(RuntimeError):
    """A Diary Note was to be created for a date that already has one."""


class Owner(Enum):
    WRITTEN = "written"
    APP = "app"
    FROZEN = "frozen"


@dataclass(frozen=True)
class SectionSpec:
    heading: str
    owner: Owner


# Every section the app knows, in note order, and who owns it (ADR-0002). The
# preamble above the first `##` heading, and any section not listed here, is
# Written. A new note's template (`new_note_body`) and a section added to an
# older note both follow this order.
SECTIONS: Tuple[SectionSpec, ...] = (
    SectionSpec("Words", Owner.WRITTEN),
    SectionSpec("Images", Owner.APP),
    SectionSpec("Location", Owner.APP),
    SectionSpec("Google Calendar events", Owner.APP),
    SectionSpec("Pocket articles", Owner.FROZEN),
    SectionSpec("Spotify tracks", Owner.APP),
)
_SECTION_RANK = {spec.heading.lower(): i for i, spec in enumerate(SECTIONS)}


def _app_owned(heading: str) -> SectionSpec:
    for spec in SECTIONS:
        if spec.heading.lower() == heading.lower():
            if spec.owner is not Owner.APP:
                raise SectionNotAppOwned(f"{spec.heading} is {spec.owner.value}")
            return spec
    raise SectionNotAppOwned(f"{heading} is not a known section, so it is written")


def new_note_body(preamble: str, contents: Dict[str, str]) -> str:
    """A new Diary Note's body: the preamble, then each section in `contents`
    in registry order, as its `## ` heading followed by its content if it has
    any. A section not in `contents` is left out of the note."""
    headings = {spec.heading for spec in SECTIONS}
    unknown = [heading for heading in contents if heading not in headings]
    if unknown:
        raise ValueError(f"not in the section registry: {unknown}")
    body = preamble
    for spec in SECTIONS:
        if spec.heading not in contents:
            continue
        body += f"## {spec.heading}\n\n"
        if contents[spec.heading]:
            body += f"{contents[spec.heading]}\n\n"
    return body


def _find_section(doc: MarkdownDoc, heading: str) -> Optional[MarkdownSection]:
    found = [s for s in doc.sections if s.title.lower() == heading.lower()]
    if len(found) > 1:
        raise ValueError(f"the note has {len(found)} {heading} sections")
    return found[0] if found else None


def _insert_section(doc: MarkdownDoc, heading: str) -> MarkdownSection:
    """Add an empty section before the first known section that comes after
    it in the registry, or at the end."""
    rank = _SECTION_RANK[heading.lower()]
    index = len(doc.sections)
    for i, sec in enumerate(doc.sections):
        if _SECTION_RANK.get(sec.title.lower(), -1) > rank:
            index = i
            break
    section = MarkdownSection([f"## {heading}", ""], title=heading, parent=doc, level=2)
    doc.sections.insert(index, section)
    return section


def _apply_sections(doc: MarkdownDoc, contents: Dict[str, str]) -> bool:
    """Write App-owned Section contents into a parsed body. True if that
    changed anything."""
    changed = False
    for heading, content in contents.items():
        section = _find_section(doc, heading)
        if section is None:
            section = _insert_section(doc, heading)
            changed = True
        if section.set_content(content) == "updated":
            changed = True
    return changed


def _unmatched_sections(body: Optional[str], contents: Dict[str, str]) -> List[str]:
    """Headings whose content in `body` isn't what this edit set."""
    doc = MarkdownDoc(body or "")
    unmatched = []
    for heading, content in contents.items():
        try:
            section = _find_section(doc, heading)
        except ValueError:
            section = None
        if section is None or section.get_content() != content:
            unmatched.append(heading)
    return unmatched


def _has_open_fence(text: str) -> bool:
    # MarkdownDoc ignores headings inside a ``` fence, the same way
    return sum(1 for line in text.split("\n") if line.startswith("```")) % 2 == 1


# How a note embeds a Joplin resource: `![](:/f04c1849b3e64b5ca151a737720c0132)`
_RESOURCE_REF = re.compile(r"!\[[^\]]*\]\(:/([a-zA-Z0-9]+?)\)")


def resource_ref(resource_id: str) -> str:
    """The markdown that embeds a resource in a note."""
    return f"![](:/{resource_id})"


def resource_ids_in(text: Optional[str]) -> List[str]:
    """The ids of the resources embedded in some markdown, in order."""
    return _RESOURCE_REF.findall(text or "")


def readable_body(body: Optional[str]) -> str:
    """A note's body with each embedded resource replaced by a text
    placeholder naming its id, for showing the note outside Joplin."""
    return _RESOURCE_REF.sub(r"[Joplin resource_id: \1]", body or "")


def _references(body: Optional[str], resource_id: str) -> bool:
    # any mention, not only an embed: a plain `[name](:/id)` link counts too
    return f":/{resource_id}" in (body or "")


# One edit at a time per note, within this process. A second edit waits for
# the first to finish, then reads the note the first one wrote.
_locks_guard = threading.Lock()
_note_locks: Dict[str, threading.Lock] = {}
_lock_holders: Dict[str, int] = {}


@contextmanager
def _note_lock(note_id: str) -> Generator[None, None, None]:
    with _locks_guard:
        lock = _note_locks.setdefault(note_id, threading.Lock())
    if _lock_holders.get(note_id) == threading.get_ident():
        # would wait on itself forever
        raise RuntimeError(f"already editing note {note_id} in this thread")
    with lock:
        try:
            _lock_holders[note_id] = threading.get_ident()
            yield
        finally:
            _lock_holders.pop(note_id, None)


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
    def find(cls, joplin: JoplinPort, dt: _Date) -> Optional["DiaryNote"]:
        """The Diary Note for a date, or None if Joplin has none."""
        if isinstance(dt, datetime):
            dt = dt.date()
        note_id = joplin.get_note_id_by_date(dt)
        if note_id is None:
            return None
        return cls(joplin=joplin, id=note_id, date=dt)

    @classmethod
    def get(cls, joplin: JoplinPort, note_id: str) -> "DiaryNote":
        """The Diary Note with this id. `LookupError` if the note isn't
        titled with a date; `JoplinError` if Joplin doesn't have it."""
        title = joplin.get_note(note_id).title
        try:
            dt = date.fromisoformat(title)
        except ValueError:
            raise LookupError(f"note {note_id} ({title!r}) is not a Diary Note")
        return cls(joplin=joplin, id=note_id, date=dt)

    @classmethod
    def create(
        cls, session: Session, joplin: JoplinPort, dt: _Date, body: str
    ) -> "DiaryNote":
        """Create the Diary Note for a date in its year's folder, then refresh
        its Note Mirror from a re-read. The body is posted as given, without
        checking it against the registry: it is either the template
        (`new_note_body`) or what the browser sends back. `NoteExists` if the
        date already has a note, and `WordsConflict` if the mirror refresh
        would raise it; either way nothing is created."""
        if isinstance(dt, datetime):
            dt = dt.date()
        title = title_from_date(dt)
        # a new note has no id yet, so this checks against the row of a
        # deleted note with the same title, as the refresh will
        check_words(session, JoplinNote(id="", title=title, body=body))
        # one create at a time: two for one day would leave two notes with the
        # same title, and two in a new year two folders for it, either of
        # which breaks the lookup of a day
        with _note_lock("new note"):
            existing = cls.find(joplin, dt)
            if existing is not None:
                raise NoteExists(
                    f"Joplin note already exists for date {dt} "
                    f"(note id: {existing.id})"
                )
            folder_id = joplin.get_or_create_year_folder(dt.year)
            note_id = joplin.create_note(title, body, folder_id)
        diary_note = cls(joplin=joplin, id=note_id, date=dt)
        diary_note.refresh_mirror(session)
        return diary_note

    def read(self) -> JoplinNote:
        return self.joplin.get_note(self.id)

    def refresh_mirror(self, session: Session, commit: bool = True) -> Tuple[int, int]:
        """Read the note and refresh its mirror. Returns the tag (added,
        removed) counts."""
        return refresh_note_mirror(session, self.joplin, self.read(), commit=commit)

    @contextmanager
    def edit(self, session: Session) -> Generator["NoteEdit", None, None]:
        """The one way to write to a Diary Note.

        ```
        with diary_note.edit(session) as edit:
            rid = edit.add_resource(png_bytes, title="map", ext="png")
            edit.drop_resource(old_rid)
            edit.set_section("Location", content)
            session.merge(OwnTracksDayMap(...))  # the caller's own rows
        ```

        Holds the note's lock throughout and reads the note on entering. On a
        clean exit it writes the note if anything changed, verifies the
        write (rewriting once, then raising `NoteClobbered`), refreshes the
        Note Mirror from the verifying read, commits the session (the
        caller's rows with the mirror), then deletes dropped resources that
        nothing else references. On any exception the session is rolled
        back and the resources this edit created are deleted, unless the
        note turned out to reference them.

        Commit your own pending writes before entering: a failed edit rolls
        back the whole session, and uncommitted SQLite writes held while
        waiting on another edit's lock would block that edit's commit.
        Autoflush is off inside the block, so rows added there reach the
        database only after Joplin has been written, and a query in the
        block doesn't see them."""
        with _note_lock(self.id):
            note = self.read()
            # the mirror refresh at the end would raise it anyway; raising
            # now means nothing has been written (checked again on the read
            # just before writing)
            check_words(session, note)
            edit = NoteEdit(self, note)
            try:
                # a flush starts SQLite's write lock, which would then be held
                # through every Joplin request until the commit
                with session.no_autoflush:
                    yield edit
                    written = edit._write(session)
                refresh_note_mirror(session, self.joplin, written, commit=False)
                session.commit()
            except BaseException:
                session.rollback()
                edit._delete_created(session)
                raise
            edit._delete_dropped(session)


class NoteEdit:
    """What one `DiaryNote.edit()` stages. Nothing reaches Joplin, other than
    new resources, until the edit exits."""

    def __init__(self, diary_note: DiaryNote, note: JoplinNote) -> None:
        self.diary_note = diary_note
        self.joplin = diary_note.joplin
        self.note = note  # as read on entering
        self.sections: Dict[str, str] = {}
        self.created: List[str] = []
        self.dropped: List[str] = []
        # whether the edit PUT the note; readable once the edit has exited
        self.wrote = False
        # the body Joplin was last seen holding
        self._last_seen = note.body

    def add_resource(
        self, data: bytes, title: Optional[str] = None, ext: str = "jpg"
    ) -> str:
        """Store a file in Joplin now and return its id, for a ref in a
        section. The id is the md5 of `data`, so bytes Joplin already has
        reuse that resource, and a failed edit leaves it alone."""
        resource_id = hashlib.md5(data).hexdigest()
        if self.joplin.resource_exists(resource_id):
            return resource_id
        resource_id = self.joplin.create_resource(data, title=title, ext=ext)
        self.created.append(resource_id)
        return resource_id

    def drop_resource(self, resource_id: str) -> None:
        """Delete a resource once the edit has been written and committed,
        unless another note still references it."""
        self.dropped.append(resource_id)

    def set_section(self, heading: str, content: str) -> None:
        """Replace an App-owned Section's whole content, adding the section
        in registry order if the note lacks it."""
        spec = _app_owned(heading)
        content = content.strip()
        doc = MarkdownDoc(f"## {spec.heading}\n\n{content}")
        if len(doc.sections) != 2 or _has_open_fence(content):
            raise ValueError(
                f"content for {spec.heading} has a `## ` heading or an unclosed "
                "``` fence, which would change the note's sections"
            )
        self.sections[spec.heading] = content

    def _write(self, session: Session) -> JoplinNote:
        """Write the note if needed and return it as Joplin then holds it."""
        # read again: the caller's block may have taken seconds, and building
        # on the body read before it would put back whatever the diarist
        # typed in Joplin meanwhile
        current = self.diary_note.read()
        self._last_seen = current.body
        # Words cleared in Joplin since entering: the mirror refresh after
        # the PUT would raise, so don't write
        check_words(session, current)
        original = current.body or ""
        if _has_open_fence(original):
            raise ValueError(
                f"note {self.note.title} has an unclosed ``` fence, so its "
                "sections can't be told apart"
            )
        doc = MarkdownDoc(original)
        # a body only goes through MarkdownDoc when a section changed: it
        # doesn't round-trip every body (one starting with `## `, say)
        body = doc.txt if _apply_sections(doc, self.sections) else original
        if body == original:
            # content decides, whatever resources were staged: dropped ones
            # are only deleted if the note no longer references them
            return current
        written = self._put_and_read(body)
        unmatched = _unmatched_sections(written.body, self.sections)
        if unmatched:
            logger.warning(
                f"note {self.note.title} lost {unmatched} right after writing; "
                "writing it again"
            )
            # onto what Joplin now holds, so a change made in the meantime
            # outside this edit's sections survives
            try:
                if _has_open_fence(written.body or ""):
                    raise ValueError("unclosed ``` fence")
                doc = MarkdownDoc(written.body or "")
                _apply_sections(doc, self.sections)
            except ValueError as e:
                # the copy written over ours can't be edited (a section twice,
                # say); call it what it is
                raise NoteClobbered(self.note.title, unmatched) from e
            written = self._put_and_read(doc.txt)
            unmatched = _unmatched_sections(written.body, self.sections)
            if unmatched:
                raise NoteClobbered(self.note.title, unmatched)
        return written

    def _put_and_read(self, body: str) -> JoplinNote:
        self.joplin.update_note_body(self.diary_note.id, body)
        self.wrote = True
        # what Joplin holds as far as we know, should the read fail
        self._last_seen = body
        written = self.diary_note.read()
        self._last_seen = written.body
        return written

    def _delete_created(self, session: Session) -> None:
        if not self.created:
            return
        # a write may have landed even though the edit failed (the read after
        # it raised, say), so ask Joplin what the note holds now
        try:
            body = self.diary_note.read().body
        except Exception:
            logger.exception(
                f"can't tell whether note {self.note.title} uses {self.created}; "
                "keeping them"
            )
            return
        for resource_id in self.created:
            if _references(body, resource_id):
                # deleting it would leave a broken image
                logger.warning(
                    f"keeping resource {resource_id}: note {self.note.title} "
                    "references it although the edit failed"
                )
                continue
            try:
                # the same photo on another day is the same resource, which a
                # concurrent edit of that note may have just used
                if self._used_by_other_notes(session, resource_id):
                    continue
                self.joplin.delete_resource(resource_id)
            except Exception:
                logger.exception(f"failed to clean up resource {resource_id}")

    def _delete_dropped(self, session: Session) -> None:
        # a created resource the written note doesn't use is dropped too
        unused = [r for r in self.created if not _references(self._last_seen, r)]
        for resource_id in dict.fromkeys(self.dropped + unused):
            try:
                if self._still_referenced(session, resource_id):
                    continue
                self.joplin.delete_resource(resource_id)
            except Exception:
                logger.exception(f"failed to delete resource {resource_id}")

    def _still_referenced(self, session: Session, resource_id: str) -> bool:
        if _references(self._last_seen, resource_id):
            logger.warning(
                f"keeping resource {resource_id}: note {self.note.title} "
                "still references it"
            )
            return True
        return self._used_by_other_notes(session, resource_id)

    def _used_by_other_notes(self, session: Session, resource_id: str) -> bool:
        # Joplin indexes note resources in the background, a few seconds
        # behind, so the mirror is asked as well
        mirrored = session.exec(
            select(JoplinNote.title).where(
                JoplinNote.id != self.diary_note.id,
                JoplinNote.body.contains(f":/{resource_id}"),
            )
        ).all()
        in_joplin = [
            note_id
            for note_id in self.joplin.get_resource_note_ids(resource_id)
            if note_id != self.diary_note.id
        ]
        if mirrored or in_joplin:
            logger.info(
                f"keeping resource {resource_id}: also used by {mirrored or in_joplin}"
            )
            return True
        return False


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
        section = MarkdownDoc(body).get_section_by_title("images")
    except KeyError:
        return []
    return resource_ids_in(section.content)


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
    # before anything flushes, so no Joplin request waits under SQLite's
    # write lock
    joplin_tags = joplin.get_note_tags(note.id)
    words = words_of(note.body)
    resource_ids = image_resource_ids_of(note.body)

    mirrored, stale, db_words = _mirrored_rows(session, note)
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
        session, note.title, joplin_tags, commit=False
    )
    if commit is True:
        session.commit()
    return added + j_added, removed + j_removed


def check_words(session: Session, note: JoplinNote) -> None:
    """Raise `WordsConflict` if refreshing the mirror from `note` would.
    Only reads."""
    mirrored, _, db_words = _mirrored_rows(session, note)
    _check_words(
        note,
        words_of(note.body),
        previous_body=mirrored.body if mirrored is not None else None,
        db_words=db_words,
    )


def _mirrored_rows(
    session: Session, note: JoplinNote
) -> Tuple[Optional[JoplinNote], Optional[JoplinNote], Optional[MyDiaryWords]]:
    """The note's mirror row, else the row of a note it replaced (same title,
    older id), and the words row of whichever there is."""
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
    return mirrored, stale, db_words


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
