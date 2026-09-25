# -*- coding: utf-8 -*-
"""DiaryNote.edit(): the one way to write to a Diary Note."""

import os
import threading
import time
from datetime import date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from mydiary.diary_note import (
    DiaryNote,
    NoteClobbered,
    SectionNotAppOwned,
    WordsConflict,
)
from mydiary.joplin_port import JoplinError
from mydiary.models import Dog, JoplinNote
from tests.in_memory_joplin import InMemoryJoplin

DAY = "2026-09-13"
BODY = (
    f"# {DAY}\n\ntimezone: UTC\n\n"
    "## Words\n\nhello\n\n"
    "## Images\n\n"
    "## Google Calendar events\n\nNone\n\n"
    "## Spotify tracks\n\nNone\n"
)


def diary_note(body: str = BODY, joplin: InMemoryJoplin = None) -> DiaryNote:
    joplin = joplin or InMemoryJoplin()
    joplin.add_note(DAY, body)
    return DiaryNote.find(joplin, date(2026, 9, 13))


def body_of(note: DiaryNote) -> str:
    return note.joplin.notes[note.id].body


def headings(body: str):
    return [line[3:] for line in body.split("\n") if line.startswith("## ")]


def dogs(session: Session):
    session.expire_all()
    return [d.name for d in session.exec(select(Dog)).all()]


class TestWrite:
    def test_sets_a_section_and_refreshes_the_mirror(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session) as edit:
            edit.set_section("Google Calendar events", "| 9:00 | 10:00 | Walk |")

        body = body_of(note)
        assert "## Google Calendar events\n\n| 9:00 | 10:00 | Walk |\n" in body
        assert "## Words\n\nhello\n" in body
        assert len(note.joplin.updates) == 1
        assert edit.wrote is True
        db_note = db_session.get(JoplinNote, note.id)
        assert db_note.body == body
        assert db_note.has_words is True

    def test_caller_rows_commit_with_the_mirror(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session) as edit:
            edit.set_section("Spotify tracks", "a song")
            db_session.add(Dog(name="Ruffles"))
        assert dogs(db_session) == ["Ruffles"]

    def test_caller_rows_are_not_flushed_while_joplin_is_called(
        self, db_session: Session
    ):
        # a flush takes SQLite's write lock, and a stalled Joplin request
        # made under it would lock every other writer out
        note = diary_note()
        joplin = note.joplin
        pending_at = []
        for name in ("update_note_body", "get_note", "get_note_tags"):
            real = getattr(joplin, name)

            def spy(*args, _real=real, _name=name, **kwargs):
                pending_at.append((_name, bool(db_session.new)))
                return _real(*args, **kwargs)

            setattr(joplin, name, spy)

        with note.edit(db_session) as edit:
            db_session.add(Dog(name="Ruffles"))
            db_session.exec(select(Dog)).all()  # would autoflush
            edit.set_section("Spotify tracks", "a song")
            pending_at.clear()  # the read on entering came before the add

        assert {name for name, _ in pending_at} == {
            "update_note_body",
            "get_note",
            "get_note_tags",
        }
        assert all(pending for _, pending in pending_at)
        assert dogs(db_session) == ["Ruffles"]

    def test_no_op_edit_makes_no_put(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session) as edit:
            edit.set_section("Google Calendar events", "None")
            db_session.add(Dog(name="Ruffles"))
        assert note.joplin.updates == []
        assert edit.wrote is False
        # the caller's rows and the mirror are still committed
        assert dogs(db_session) == ["Ruffles"]
        assert db_session.get(JoplinNote, note.id).body == BODY

    def test_a_body_markdown_does_not_round_trip_is_left_alone(
        self, db_session: Session
    ):
        body = "## Words\n\nhello\n\n## Spotify tracks\n\nNone\n"
        note = diary_note(body)
        with note.edit(db_session) as edit:
            edit.set_section("Spotify tracks", "None")
        assert note.joplin.updates == []
        assert body_of(note) == body

    def test_a_note_clobbered_back_later_is_written_again(self, db_session: Session):
        # the check before writing looks at the note's content, not the
        # database, so a stale copy written back after an edit is seen
        note = diary_note()
        with note.edit(db_session) as edit:
            edit.set_section("Spotify tracks", "a song")
        note.joplin.edit_note(note.id, BODY)

        with note.edit(db_session) as edit:
            edit.set_section("Spotify tracks", "a song")

        assert len(note.joplin.updates) == 2
        assert "## Spotify tracks\n\na song\n" in body_of(note)

    def test_text_typed_during_the_edit_survives(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session) as edit:
            # the caller's block can take seconds (a map render, downloads)
            note.joplin.edit_note(
                note.id, BODY.replace("hello", "hello, typed meanwhile")
            )
            edit.set_section("Spotify tracks", "a song")
        body = body_of(note)
        assert "hello, typed meanwhile" in body
        assert "## Spotify tracks\n\na song\n" in body

    def test_staged_resources_alone_make_no_put(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session) as edit:
            rid = edit.add_resource(b"photo")
            edit.drop_resource(rid)
        assert note.joplin.updates == []

    def test_a_created_resource_the_note_does_not_use_is_deleted(
        self, db_session: Session
    ):
        note = diary_note()
        with note.edit(db_session) as edit:
            rid = edit.add_resource(b"photo")
            edit.set_section("Spotify tracks", "a song")
        assert not note.joplin.resource_exists(rid)


class TestClobber:
    def test_clobbered_once_is_rewritten_onto_the_new_body(self, db_session: Session):
        note = diary_note()
        # the Joplin app writes back its copy, in which the diarist has typed
        typed = BODY.replace("hello", "hello, typed meanwhile")
        note.joplin.clobber_next_update(note.id, typed)

        with note.edit(db_session) as edit:
            edit.set_section("Spotify tracks", "a song")

        body = body_of(note)
        assert len(note.joplin.updates) == 2
        assert "## Spotify tracks\n\na song\n" in body
        assert "hello, typed meanwhile" in body
        assert db_session.get(JoplinNote, note.id).body == body

    def test_clobbered_twice_raises_and_undoes_the_edit(self, db_session: Session):
        joplin = InMemoryJoplin()
        old = joplin.create_resource(b"old map", ext="png")
        note = diary_note(
            BODY.replace("## Images\n", f"## Images\n\n![](:/{old})\n"), joplin
        )
        stale = body_of(note)
        joplin.clobber_next_update(note.id, stale)
        joplin.clobber_next_update(note.id, stale)

        with pytest.raises(NoteClobbered) as e:
            with note.edit(db_session) as edit:
                new = edit.add_resource(b"new map", ext="png")
                edit.drop_resource(old)
                edit.set_section("Images", f"![](:/{new})")
                db_session.add(Dog(name="Ruffles"))

        assert e.value.headings == ["Images"]
        assert body_of(note) == stale
        assert dogs(db_session) == []
        assert db_session.get(JoplinNote, note.id) is None
        # the stale body never references the new resource, and still
        # references the old one
        assert not joplin.resource_exists(new)
        assert joplin.resource_exists(old)

    def test_a_clobbering_copy_with_a_section_twice_is_a_clobber(
        self, db_session: Session
    ):
        note = diary_note()
        twice = BODY + "\n## Spotify tracks\n\nNone\n"
        note.joplin.clobber_next_update(note.id, twice)
        with pytest.raises(NoteClobbered):
            with note.edit(db_session) as edit:
                edit.set_section("Spotify tracks", "a song")


class TestFailure:
    def test_failed_put(self, db_session: Session):
        note = diary_note()
        note.joplin.fail_next_update()
        with pytest.raises(JoplinError):
            with note.edit(db_session) as edit:
                rid = edit.add_resource(b"photo")
                edit.set_section("Images", f"![](:/{rid})")
                db_session.add(Dog(name="Ruffles"))
        assert body_of(note) == BODY
        assert dogs(db_session) == []
        assert not note.joplin.resource_exists(rid)

    def test_caller_exception_writes_nothing(self, db_session: Session):
        note = diary_note()
        with pytest.raises(ZeroDivisionError):
            with note.edit(db_session) as edit:
                rid = edit.add_resource(b"photo")
                edit.set_section("Images", f"![](:/{rid})")
                db_session.add(Dog(name="Ruffles"))
                1 / 0
        assert note.joplin.updates == []
        assert dogs(db_session) == []
        assert not note.joplin.resource_exists(rid)

    def test_a_reused_resource_survives_a_failed_edit(self, db_session: Session):
        joplin = InMemoryJoplin()
        existing = joplin.create_resource(b"photo")
        note = diary_note(joplin=joplin)
        with pytest.raises(ZeroDivisionError):
            with note.edit(db_session) as edit:
                assert edit.add_resource(b"photo") == existing
                1 / 0
        assert joplin.resource_exists(existing)

    def test_a_created_resource_the_note_ended_up_with_is_kept(
        self, db_session: Session
    ):
        note = diary_note()
        with note.edit(db_session):
            pass  # mirror "hello"
        # right after the write lands, the Words are cleared in Joplin: the
        # write verifies, then the mirror refresh raises
        with pytest.raises(WordsConflict):
            with note.edit(db_session) as edit:
                rid = edit.add_resource(b"photo")
                edit.set_section("Images", f"![](:/{rid})")
                note.joplin.clobber_next_update(
                    note.id,
                    BODY.replace("hello", "").replace(
                        "## Images\n", f"## Images\n\n![](:/{rid})\n"
                    ),
                )
        # the note shows it, so deleting it would leave a broken image
        assert note.joplin.resource_exists(rid)

    def test_a_write_that_landed_keeps_its_resource_when_the_read_after_fails(
        self, db_session: Session
    ):
        note = diary_note()
        joplin = note.joplin
        get_note = joplin.get_note
        reads = []

        def flaky_get_note(note_id):
            reads.append(note_id)
            if len(reads) == 3:  # entering, before writing, then after the PUT
                raise JoplinError("timed out")
            return get_note(note_id)

        joplin.get_note = flaky_get_note
        with pytest.raises(JoplinError):
            with note.edit(db_session) as edit:
                rid = edit.add_resource(b"photo")
                edit.set_section("Images", f"![](:/{rid})")
        assert f":/{rid}" in body_of(note)
        assert joplin.resource_exists(rid)

    def test_created_resources_are_kept_when_the_note_cant_be_read(
        self, db_session: Session
    ):
        note = diary_note()
        joplin = note.joplin
        get_note = joplin.get_note
        reads = []

        def failing_after_the_put(note_id):
            reads.append(note_id)
            if len(reads) >= 3:
                raise JoplinError("Joplin went away")
            return get_note(note_id)

        joplin.get_note = failing_after_the_put
        with pytest.raises(JoplinError):
            with note.edit(db_session) as edit:
                rid = edit.add_resource(b"photo")
                edit.set_section("Images", f"![](:/{rid})")
        assert joplin.resource_exists(rid)

    def test_a_created_resource_another_note_took_up_is_kept(
        self, db_session: Session
    ):
        # the same photo on two days is one resource: an edit of the other
        # day can pick up the one this edit created before this one fails
        note = diary_note()
        joplin = note.joplin
        with pytest.raises(JoplinError):
            with note.edit(db_session) as edit:
                rid = edit.add_resource(b"photo")
                joplin.add_note("2026-09-14", f"## Images\n\n![](:/{rid})\n")
                edit.set_section("Images", f"![](:/{rid})")
                joplin.fail_next_update()
        assert joplin.resource_exists(rid)

    def test_dropped_resources_survive_a_failed_edit(self, db_session: Session):
        joplin = InMemoryJoplin()
        old = joplin.create_resource(b"old photo")
        note = diary_note(
            BODY.replace("## Images\n", f"## Images\n\n![](:/{old})\n"), joplin
        )
        with note.edit(db_session):
            pass  # mirror "hello"
        # the write verifies without `old`, then the mirror refresh raises
        joplin.clobber_next_update(note.id, BODY.replace("hello", ""))
        with pytest.raises(WordsConflict):
            with note.edit(db_session) as edit:
                edit.drop_resource(old)
                edit.set_section("Images", "")
        assert f":/{old}" not in body_of(note)
        assert joplin.resource_exists(old)


class TestDroppedResources:
    def with_photo(self, joplin: InMemoryJoplin, resource_id: str) -> DiaryNote:
        body = BODY.replace("## Images\n", f"## Images\n\n![](:/{resource_id})\n")
        return diary_note(body, joplin)

    def test_deleted_after_the_write(self, db_session: Session):
        joplin = InMemoryJoplin()
        rid = joplin.create_resource(b"photo")
        note = self.with_photo(joplin, rid)
        with note.edit(db_session) as edit:
            edit.drop_resource(rid)
            edit.set_section("Images", "")
        assert not joplin.resource_exists(rid)

    def test_kept_while_this_note_still_references_it(self, db_session: Session):
        joplin = InMemoryJoplin()
        rid = joplin.create_resource(b"photo")
        note = self.with_photo(joplin, rid)
        with note.edit(db_session) as edit:
            edit.drop_resource(rid)
        assert joplin.resource_exists(rid)

    def test_kept_when_another_note_references_it(self, db_session: Session):
        joplin = InMemoryJoplin()
        rid = joplin.create_resource(b"photo")
        note = self.with_photo(joplin, rid)
        # the same photo on another day shares the resource
        joplin.add_note("2026-09-14", f"## Images\n\n![](:/{rid})\n")
        with note.edit(db_session) as edit:
            edit.drop_resource(rid)
            edit.set_section("Images", "")
        assert joplin.resource_exists(rid)

    def test_kept_when_only_the_mirror_knows_another_note_uses_it(
        self, db_session: Session
    ):
        # Joplin's resource index lags a few seconds behind a save
        joplin = InMemoryJoplin()
        rid = joplin.create_resource(b"photo")
        note = self.with_photo(joplin, rid)
        db_session.add(
            JoplinNote(
                id="other",
                parent_id="folder",
                title="2026-09-14",
                body=f"## Images\n\n![](:/{rid})\n",
                created_time=datetime(2026, 9, 14),
                updated_time=datetime(2026, 9, 14),
            )
        )
        db_session.commit()
        with note.edit(db_session) as edit:
            edit.drop_resource(rid)
            edit.set_section("Images", "")
        assert joplin.resource_exists(rid)

    def test_a_failed_delete_is_logged_not_raised(self, db_session: Session, caplog):
        note = diary_note()
        with note.edit(db_session) as edit:
            edit.drop_resource("f" * 32)  # Joplin has no such resource
            db_session.add(Dog(name="Ruffles"))
        assert dogs(db_session) == ["Ruffles"]
        assert "failed to delete resource" in caplog.text


class TestSections:
    def test_missing_section_goes_in_registry_order(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session) as edit:
            edit.set_section("Location", "a map")
        assert headings(body_of(note)) == [
            "Words",
            "Images",
            "Location",
            "Google Calendar events",
            "Spotify tracks",
        ]
        assert "## Location\n\na map\n\n## Google Calendar events" in body_of(note)

    def test_missing_section_goes_last_when_nothing_follows_it(
        self, db_session: Session
    ):
        note = diary_note(f"# {DAY}\n\n## Words\n\nhello\n")
        with note.edit(db_session) as edit:
            edit.set_section("Spotify tracks", "a song")
        assert body_of(note) == (
            f"# {DAY}\n\n## Words\n\nhello\n\n## Spotify tracks\n\na song\n"
        )

    def test_unknown_sections_keep_their_place(self, db_session: Session):
        note = diary_note(
            f"# {DAY}\n\n## Words\n\nhello\n\n## Dreams\n\nflying\n\n"
            "## Spotify tracks\n\nNone\n"
        )
        with note.edit(db_session) as edit:
            edit.set_section("Images", "photos")
        assert headings(body_of(note)) == [
            "Words",
            "Dreams",
            "Images",
            "Spotify tracks",
        ]

    def test_headings_match_whatever_their_case(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session) as edit:
            edit.set_section("spotify TRACKS", "a song")
        assert headings(body_of(note)).count("Spotify tracks") == 1
        assert "a song" in body_of(note)

    @pytest.mark.parametrize("heading", ["Words", "Pocket articles", "Dreams"])
    def test_only_app_owned_sections_can_be_set(self, db_session: Session, heading):
        note = diary_note()
        with pytest.raises(SectionNotAppOwned):
            with note.edit(db_session) as edit:
                edit.set_section(heading, "overwritten")
        assert note.joplin.updates == []

    @pytest.mark.parametrize(
        "content", ["photo\n\n## Spotify tracks\n\nmore", "```\nunclosed"]
    )
    def test_content_that_would_change_the_sections_raises(
        self, db_session: Session, content
    ):
        note = diary_note()
        with pytest.raises(ValueError):
            with note.edit(db_session) as edit:
                edit.set_section("Images", content)
        assert note.joplin.updates == []

    def test_a_note_with_an_unclosed_fence_is_not_written(self, db_session: Session):
        note = diary_note(BODY.replace("hello", "```\nhello"))
        with pytest.raises(ValueError, match="fence"):
            with note.edit(db_session) as edit:
                edit.set_section("Spotify tracks", "a song")
        assert note.joplin.updates == []


class TestConcurrency:
    def test_two_threads_editing_one_note_both_land(self, tmp_path):
        engine = create_engine(
            f"sqlite:///{tmp_path / 'db.sqlite'}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        note = diary_note()
        joplin = note.joplin
        first_putting = threading.Event()
        put = joplin.update_note_body

        def slow_first_put(note_id, body):
            # the first edit has read the note and built its body; without
            # the lock the second edit reads and writes now, and this PUT then
            # drops the second one's section
            if not first_putting.is_set():
                first_putting.set()
                time.sleep(0.2)
            put(note_id, body)

        joplin.update_note_body = slow_first_put
        errors = []

        def first():
            with Session(engine) as session, note.edit(session) as edit:
                edit.set_section("Google Calendar events", "calendar")

        def second():
            first_putting.wait()
            with Session(engine) as session, note.edit(session) as edit:
                edit.set_section("Spotify tracks", "music")

        def run(f):
            try:
                f()
            except Exception as e:  # pragma: no cover - reported below
                errors.append(e)

        threads = [
            threading.Thread(target=run, args=(f,), daemon=True)
            for f in (first, second)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert not any(t.is_alive() for t in threads)
        assert errors == []
        body = body_of(note)
        assert "## Google Calendar events\n\ncalendar\n" in body
        assert "## Spotify tracks\n\nmusic\n" in body

    def test_a_nested_edit_of_the_same_note_raises(self, db_session: Session):
        import mydiary.diary_note as diary_note_module

        note = diary_note()
        with pytest.raises(RuntimeError, match="already editing"):
            with note.edit(db_session):
                with note.edit(db_session):
                    pass
        # and the outer edit released the lock
        assert not diary_note_module._note_locks[note.id].locked()
        assert note.id not in diary_note_module._lock_holders


class TestWordsCheckOnEntering:
    def test_a_words_conflict_on_entering_writes_nothing(self, db_session: Session):
        note = diary_note()
        with note.edit(db_session):
            pass  # mirror "hello"
        note.joplin.edit_note(note.id, BODY.replace("hello", ""))

        with pytest.raises(WordsConflict):
            with note.edit(db_session) as edit:  # pragma: no cover
                edit.set_section("Spotify tracks", "a song")
        assert note.joplin.updates == []

    def test_words_cleared_during_the_edit_stop_it_before_writing(
        self, db_session: Session
    ):
        note = diary_note()
        with note.edit(db_session):
            pass  # mirror "hello"
        with pytest.raises(WordsConflict):
            with note.edit(db_session) as edit:
                rid = edit.add_resource(b"photo")
                edit.set_section("Images", f"![](:/{rid})")
                note.joplin.edit_note(note.id, BODY.replace("hello", ""))
        assert note.joplin.updates == []
        assert not note.joplin.resource_exists(rid)
