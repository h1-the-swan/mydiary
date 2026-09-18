# -*- coding: utf-8 -*-
"""The Joplin -> database note sync that feeds the tag system."""

from datetime import datetime, timedelta

from sqlmodel import Session, select

from mydiary.models import JoplinNote, MyDiaryWords
from mydiary.tags import tags_for_target
from tests.fakes import FakeJoplin, make_note

WORDS = "# 2026-09-13\n\n## Words\n\nWalked #dog:Ruffles today.\n\n## Images\n\n"


def words_rows(session: Session):
    return session.exec(select(MyDiaryWords)).all()


class TestSyncOneNote:
    def test_mirrors_the_note_and_its_tags(self, db_session: Session):
        joplin = FakeJoplin([make_note("2026-09-13", WORDS)])
        added, removed = joplin.sync_note_api_to_db_obj("note-2026-09-13", db_session)
        assert (added, removed) == (1, 0)

        db_note = db_session.get(JoplinNote, "note-2026-09-13")
        assert db_note.body == WORDS
        assert db_note.body_hash is not None
        assert db_note.has_words is True
        assert db_note.has_images is False
        assert db_note.time_last_api_sync is not None
        (words,) = words_rows(db_session)
        assert words.txt == "Walked #dog:Ruffles today."
        assert [t.key for t, _ in tags_for_target(db_session, "day", "2026-09-13")] == [
            "dog:ruffles"
        ]

    def test_changed_words_update_the_same_row(self, db_session: Session):
        note = make_note("2026-09-13", WORDS)
        joplin = FakeJoplin([note])
        joplin.sync_note_api_to_db_obj(note.id, db_session)
        (before,) = words_rows(db_session)
        before_id, before_hash = before.id, before.hash

        note.body = WORDS.replace("Walked #dog:Ruffles today.", "Stayed in. #rain")
        note.updated_time = note.updated_time + timedelta(hours=1)
        added, removed = joplin.sync_note_api_to_db_obj(note.id, db_session)
        assert (added, removed) == (1, 1)

        (after,) = words_rows(db_session)  # one row, not one per edit
        assert after.id == before_id
        assert after.txt == "Stayed in. #rain"
        assert after.hash != before_hash
        assert after.updated_at == note.updated_time
        assert [t.key for t, _ in tags_for_target(db_session, "day", "2026-09-13")] == ["rain"]

    def test_unchanged_words_leave_the_row_alone(self, db_session: Session):
        note = make_note("2026-09-13", WORDS)
        joplin = FakeJoplin([note])
        joplin.sync_note_api_to_db_obj(note.id, db_session)
        (before,) = words_rows(db_session)
        snapshot = (before.id, before.hash, before.updated_at)
        joplin.sync_note_api_to_db_obj(note.id, db_session)
        (after,) = words_rows(db_session)
        assert (after.id, after.hash, after.updated_at) == snapshot

    def test_note_without_a_words_section(self, db_session: Session):
        joplin = FakeJoplin([make_note("2026-09-13", "# 2026-09-13\n\n## Images\n\n#photo\n")])
        joplin.sync_note_api_to_db_obj("note-2026-09-13", db_session)
        db_note = db_session.get(JoplinNote, "note-2026-09-13")
        assert db_note.has_words is False
        assert words_rows(db_session) == []
        assert [t.key for t, _ in tags_for_target(db_session, "day", "2026-09-13")] == ["photo"]

    def test_empty_body(self, db_session: Session):
        joplin = FakeJoplin([make_note("2026-09-13", None)])
        assert joplin.sync_note_api_to_db_obj("note-2026-09-13", db_session) == (0, 0)
        assert db_session.get(JoplinNote, "note-2026-09-13").has_words is False

    def test_recreated_note_keeps_the_day_under_its_new_id(self, db_session: Session):
        old = make_note("2026-09-13", WORDS, note_id="old-id")
        FakeJoplin([old]).sync_note_api_to_db_obj("old-id", db_session)
        (words_before,) = words_rows(db_session)

        # deleted and re-created in Joplin: same title, new id, same words
        new = make_note("2026-09-13", WORDS, note_id="new-id")
        FakeJoplin([new]).sync_note_api_to_db_obj("new-id", db_session)

        assert db_session.get(JoplinNote, "old-id") is None
        assert db_session.get(JoplinNote, "new-id").title == "2026-09-13"
        (words_after,) = words_rows(db_session)
        assert words_after.id == words_before.id
        assert words_after.joplin_note_id == "new-id"
        # the day's tags are keyed by title, so nothing about them changed
        assert [t.key for t, _ in tags_for_target(db_session, "day", "2026-09-13")] == [
            "dog:ruffles"
        ]


class TestSyncAllNotes:
    def test_fetches_only_what_changed(self, db_session: Session):
        a = make_note("2026-09-11", "## Words\n\n#a\n")
        b = make_note("2026-09-12", "## Words\n\n#b\n")
        joplin = FakeJoplin([a, b])
        first = joplin.sync_notes_from_api(db_session)
        assert (first.notes_checked, first.notes_synced, first.tags_added) == (2, 2, 2)

        again = joplin.sync_notes_from_api(db_session)
        assert (again.notes_checked, again.notes_synced, again.tags_added) == (2, 0, 0)

        # one edited in Joplin, one new
        b.body = "## Words\n\n#b #bb\n"
        b.updated_time = b.updated_time + timedelta(minutes=5)
        joplin.notes.append(make_note("2026-09-13", "## Words\n\n#c\n"))
        third = joplin.sync_notes_from_api(db_session)
        assert (third.notes_checked, third.notes_synced, third.tags_added) == (3, 2, 2)

    def test_force_syncs_everything(self, db_session: Session):
        joplin = FakeJoplin([make_note("2026-09-11", "#a"), make_note("2026-09-12", "#b")])
        joplin.sync_notes_from_api(db_session)
        forced = joplin.sync_notes_from_api(db_session, force=True)
        assert (forced.notes_checked, forced.notes_synced, forced.tags_added) == (2, 2, 0)

    def test_rows_without_a_body_or_a_sync_time_are_fetched(self, db_session: Session):
        note = make_note("2026-09-11", "#a")
        # a mirror row from before bodies were stored: same updated_time, no body
        stale = JoplinNote.model_validate(note.model_dump())
        stale.body = None
        stale.body_hash = None
        db_session.add(stale)
        db_session.commit()

        summary = FakeJoplin([note]).sync_notes_from_api(db_session)
        assert summary.notes_synced == 1
        assert db_session.get(JoplinNote, note.id).body == "#a"

    def test_one_day(self, db_session: Session):
        joplin = FakeJoplin([make_note("2026-09-11", "#a")])
        summary = joplin.sync_one_day(db_session, datetime(2026, 9, 11))
        assert (summary.notes_checked, summary.notes_synced, summary.tags_added) == (1, 1, 1)
        missing = joplin.sync_one_day(db_session, datetime(2026, 1, 1))
        assert (missing.notes_checked, missing.notes_synced) == (0, 0)


class TestJoplinNoteTags:
    """Joplin's own note-level tags, one way: Joplin -> mydiary."""

    def test_note_tags_become_joplin_links(self, db_session: Session):
        note = make_note("2026-09-13", WORDS)
        joplin = FakeJoplin([note], tags={note.id: ["Hiking", "book:The Husbands"]})
        added, removed = joplin.sync_note_api_to_db_obj(note.id, db_session)
        assert (added, removed) == (3, 0)  # the hashtag plus two Joplin tags
        got = {t.key: (t.name, src) for t, src in tags_for_target(db_session, "day", "2026-09-13")}
        assert got == {
            "dog:ruffles": ("ruffles", "note"),
            "hiking": ("Hiking", "joplin"),
            "book:the-husbands": ("book:The Husbands", "joplin"),
        }

    def test_tag_removed_in_joplin_removes_only_its_link(self, db_session: Session):
        from mydiary.tags import set_target_tags

        note = make_note("2026-09-13", "no hashtags")
        joplin = FakeJoplin([note], tags={note.id: ["hiking", "rain"]})
        joplin.sync_note_api_to_db_obj(note.id, db_session)
        set_target_tags(db_session, "day", "2026-09-13", ["manual-one"])

        joplin.note_tags[note.id] = ["rain"]
        assert joplin.sync_note_api_to_db_obj(note.id, db_session) == (0, 1)
        assert sorted(t.key for t, _ in tags_for_target(db_session, "day", "2026-09-13")) == [
            "manual-one",
            "rain",
        ]

    def test_hashtag_and_joplin_tag_with_the_same_key_share_one_link(self, db_session: Session):
        note = make_note("2026-09-13", "## Words\n\n#hiking\n")
        joplin = FakeJoplin([note], tags={note.id: ["hiking"]})
        joplin.sync_note_api_to_db_obj(note.id, db_session)
        ((tag, source),) = tags_for_target(db_session, "day", "2026-09-13")
        assert (tag.key, source) == ("hiking", "note")
        # the hashtag goes, the Joplin tag stays: the link changes hands
        note.body = "## Words\n\nnothing\n"
        joplin.sync_note_api_to_db_obj(note.id, db_session)
        ((tag, source),) = tags_for_target(db_session, "day", "2026-09-13")
        assert (tag.key, source) == ("hiking", "joplin")

    def test_full_sync_sees_a_tag_change_without_a_body_change(self, db_session: Session):
        note = make_note("2026-09-13", "## Words\n\nplain\n")
        joplin = FakeJoplin([note])
        joplin.sync_notes_from_api(db_session)
        assert tags_for_target(db_session, "day", "2026-09-13") == []

        # tagging a note in Joplin does not touch its updated_time
        joplin.note_tags[note.id] = ["hiking"]
        summary = joplin.sync_notes_from_api(db_session)
        assert (summary.notes_synced, summary.tags_added) == (0, 1)
        assert [(t.key, s) for t, s in tags_for_target(db_session, "day", "2026-09-13")] == [
            ("hiking", "joplin")
        ]

        joplin.note_tags[note.id] = []
        summary = joplin.sync_notes_from_api(db_session)
        assert (summary.tags_added, summary.tags_removed) == (0, 1)
        assert tags_for_target(db_session, "day", "2026-09-13") == []

    def test_tags_on_notes_outside_the_diary_are_ignored(self, db_session: Session):
        note = make_note("2026-09-13", "plain")
        joplin = FakeJoplin([note], tags={"some-other-note": ["hiking"]})
        joplin.sync_notes_from_api(db_session)
        from mydiary.models import TagLink
        assert db_session.exec(select(TagLink)).all() == []
