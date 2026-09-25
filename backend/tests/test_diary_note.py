# -*- coding: utf-8 -*-
"""The Diary Note module: lookup by date and the Note Mirror refresh."""

import logging
from datetime import date, datetime

import pytest
from sqlmodel import Session, select

from mydiary.diary_note import (
    DiaryNote,
    WordsConflict,
    refresh_note_mirror,
    sync_changed_notes,
    sync_one_day,
)
from mydiary.models import (
    JoplinNote,
    JoplinNoteImageLink,
    MyDiaryImage,
    MyDiaryWords,
    TagLink,
)
from mydiary.tags import set_target_tags, tags_for_target
from tests.in_memory_joplin import InMemoryJoplin

DAY = "2026-09-13"
WORDS = "# 2026-09-13\n\n## Words\n\nWalked #dog:Ruffles today.\n\n## Images\n\n"


def words_rows(session: Session):
    return session.exec(select(MyDiaryWords)).all()


def refresh(session: Session, joplin: InMemoryJoplin, note_id: str):
    return refresh_note_mirror(session, joplin, joplin.get_note(note_id))


def day_tags(session: Session):
    return [t.key for t, _ in tags_for_target(session, "day", DAY)]


def with_words(words: str) -> str:
    return f"# {DAY}\n\n## Words\n\n{words}\n\n## Images\n\n"


class TestFind:
    def test_found_by_date(self):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, WORDS)
        diary_note = DiaryNote.find(joplin, datetime(2026, 9, 13, 8, 30))
        assert (diary_note.id, diary_note.date) == (note_id, date(2026, 9, 13))

    def test_missing_is_none(self):
        assert DiaryNote.find(InMemoryJoplin(), date(2026, 9, 13)) is None


class TestRefreshMirror:
    def test_mirrors_the_note_and_its_tags(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, WORDS)
        assert refresh(db_session, joplin, note_id) == (1, 0)

        db_note = db_session.get(JoplinNote, note_id)
        assert db_note.body == WORDS
        assert db_note.body_hash is not None
        assert db_note.has_words is True
        assert db_note.has_images is False
        assert db_note.time_last_api_sync is not None
        (words,) = words_rows(db_session)
        assert words.txt == "Walked #dog:Ruffles today."
        assert day_tags(db_session) == ["dog:ruffles"]

    def test_changed_words_update_the_same_row(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, WORDS)
        refresh(db_session, joplin, note_id)
        (before,) = words_rows(db_session)
        before_id, before_hash = before.id, before.hash

        joplin.edit_note(note_id, with_words("Stayed in. #rain"))
        assert refresh(db_session, joplin, note_id) == (1, 1)

        (after,) = words_rows(db_session)  # one row, not one per edit
        assert after.id == before_id
        assert after.txt == "Stayed in. #rain"
        assert after.hash != before_hash
        assert after.updated_at == joplin.notes[note_id].updated_time
        assert day_tags(db_session) == ["rain"]

    def test_unchanged_words_leave_the_row_alone(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, WORDS)
        refresh(db_session, joplin, note_id)
        (before,) = words_rows(db_session)
        snapshot = (before.id, before.hash, before.updated_at)
        refresh(db_session, joplin, note_id)
        (after,) = words_rows(db_session)
        assert (after.id, after.hash, after.updated_at) == snapshot

    def test_note_without_a_words_section(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, f"# {DAY}\n\n## Images\n\n#photo\n")
        refresh(db_session, joplin, note_id)
        assert db_session.get(JoplinNote, note_id).has_words is False
        assert words_rows(db_session) == []
        assert day_tags(db_session) == ["photo"]

    @pytest.mark.parametrize("body", ["", None])
    def test_empty_body(self, db_session: Session, body):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, "")
        note = joplin.get_note(note_id)
        note.body = body
        assert refresh_note_mirror(db_session, joplin, note) == (0, 0)
        db_note = db_session.get(JoplinNote, note_id)
        assert (db_note.has_words, db_note.has_images) == (False, False)

    def test_recreated_note_keeps_the_day_under_its_new_id(self, db_session: Session):
        joplin = InMemoryJoplin()
        old_id = joplin.add_note(DAY, WORDS)
        refresh(db_session, joplin, old_id)
        (words_before,) = words_rows(db_session)

        # deleted and re-created in Joplin: same title, new id, same words
        del joplin.notes[old_id]
        new_id = joplin.add_note(DAY, WORDS)
        refresh(db_session, joplin, new_id)

        assert db_session.get(JoplinNote, old_id) is None
        assert db_session.get(JoplinNote, new_id).title == DAY
        (words_after,) = words_rows(db_session)
        assert words_after.id == words_before.id
        assert words_after.joplin_note_id == new_id
        # the day's tags are keyed by title, so nothing about them changed
        assert day_tags(db_session) == ["dog:ruffles"]


def add_image(session: Session, resource_id: str) -> MyDiaryImage:
    image = MyDiaryImage(
        hash=f"hash-{resource_id}",
        name=resource_id,
        nextcloud_path=f"H1phone_sync/2026/09/{resource_id}.jpg",
        thumbnail_size=1000,
        joplin_resource_id=resource_id,
        created_at=datetime(2026, 9, 13, 12, 0, 0),
    )
    session.add(image)
    session.commit()
    return image


def with_images(*resource_ids: str) -> str:
    refs = "\n\n".join(f"![](:/{rid})" for rid in resource_ids)
    return f"# {DAY}\n\n## Words\n\n## Images\n\n{refs}\n"


def linked_images(session: Session, note_id: str):
    links = session.exec(
        select(JoplinNoteImageLink)
        .where(JoplinNoteImageLink.joplin_note_id == note_id)
        .order_by(JoplinNoteImageLink.sequence_num)
    ).all()
    return [
        (
            link.sequence_num,
            session.get(MyDiaryImage, link.mydiary_image_id).joplin_resource_id,
        )
        for link in links
    ]


class TestImageLinks:
    def test_links_follow_the_images_section_in_order(self, db_session: Session):
        a = "a" * 32
        b = "b" * 32
        legacy = "c" * 32  # no MyDiaryImage row, like the old Google Photos refs
        add_image(db_session, a)
        add_image(db_session, b)
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_images(b, legacy, a))

        refresh(db_session, joplin, note_id)

        assert linked_images(db_session, note_id) == [(1, b), (2, a)]
        assert db_session.get(JoplinNote, note_id).has_images is True

    def test_reordered_and_removed_by_hand_in_joplin(self, db_session: Session):
        a, b, c = "a" * 32, "b" * 32, "c" * 32
        for rid in (a, b, c):
            add_image(db_session, rid)
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_images(a, b, c))
        refresh(db_session, joplin, note_id)

        joplin.edit_note(note_id, with_images(c, a))
        refresh(db_session, joplin, note_id)

        assert linked_images(db_session, note_id) == [(1, c), (2, a)]

    def test_a_link_replaced_under_the_same_key(self, db_session: Session):
        # (note, a, 1) is deleted and added back in the same rebuild
        a, b, c = "a" * 32, "b" * 32, "c" * 32
        for rid in (a, b, c):
            add_image(db_session, rid)
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_images(a, b))
        refresh(db_session, joplin, note_id)

        joplin.edit_note(note_id, with_images(a, c))
        refresh(db_session, joplin, note_id)

        db_session.expire_all()
        assert linked_images(db_session, note_id) == [(1, a), (2, c)]

    def test_a_repeated_ref_is_linked_once(self, db_session: Session):
        a, b = "a" * 32, "b" * 32
        add_image(db_session, a)
        add_image(db_session, b)
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_images(a, b, a))
        refresh(db_session, joplin, note_id)
        assert linked_images(db_session, note_id) == [(1, a), (2, b)]

    def test_only_legacy_refs(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_images("c" * 32))
        refresh(db_session, joplin, note_id)
        assert linked_images(db_session, note_id) == []
        # the note does show an image, even one the database doesn't know
        assert db_session.get(JoplinNote, note_id).has_images is True

    def test_all_photos_removed(self, db_session: Session):
        a = "a" * 32
        add_image(db_session, a)
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_images(a))
        refresh(db_session, joplin, note_id)

        joplin.edit_note(note_id, with_images())
        refresh(db_session, joplin, note_id)

        assert linked_images(db_session, note_id) == []
        assert db_session.get(JoplinNote, note_id).has_images is False

    def test_recreated_note_links_move_to_the_new_id(self, db_session: Session):
        a = "a" * 32
        add_image(db_session, a)
        joplin = InMemoryJoplin()
        old_id = joplin.add_note(DAY, with_images(a))
        refresh(db_session, joplin, old_id)

        del joplin.notes[old_id]
        new_id = joplin.add_note(DAY, with_images(a))
        refresh(db_session, joplin, new_id)

        assert linked_images(db_session, old_id) == []
        assert linked_images(db_session, new_id) == [(1, a)]


class TestWordsCheck:
    """The mirror's words must equal the Words of the note last mirrored."""

    def mirrored(self, session: Session, words: str):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_words(words))
        refresh(session, joplin, note_id)
        return joplin, note_id

    def assert_untouched(self, session: Session, note_id: str, body: str, words: str):
        session.expire_all()
        assert session.get(JoplinNote, note_id).body == body
        assert [w.txt for w in words_rows(session)] == [words]

    def test_a_normal_edit_in_joplin_passes(self, db_session: Session):
        joplin, note_id = self.mirrored(db_session, "first draft")
        joplin.edit_note(note_id, with_words("second draft"))
        refresh(db_session, joplin, note_id)
        assert [w.txt for w in words_rows(db_session)] == ["second draft"]

    def test_cleared_words_raise(self, db_session: Session):
        joplin, note_id = self.mirrored(db_session, "only copy")
        joplin.edit_note(note_id, with_words(""))
        with pytest.raises(WordsConflict):
            refresh(db_session, joplin, note_id)
        self.assert_untouched(db_session, note_id, with_words("only copy"), "only copy")

    def test_a_missing_words_section_raises(self, db_session: Session):
        joplin, note_id = self.mirrored(db_session, "only copy")
        joplin.edit_note(note_id, f"# {DAY}\n\n## Images\n\n")
        with pytest.raises(WordsConflict):
            refresh(db_session, joplin, note_id)
        self.assert_untouched(db_session, note_id, with_words("only copy"), "only copy")

    def test_words_written_by_something_else_raise(self, db_session: Session):
        joplin, note_id = self.mirrored(db_session, "from the note")
        (row,) = words_rows(db_session)
        row.txt = "written straight to the database"
        db_session.add(row)
        db_session.commit()

        joplin.edit_note(note_id, with_words("edited in joplin"))
        with pytest.raises(WordsConflict):
            refresh(db_session, joplin, note_id)
        self.assert_untouched(
            db_session,
            note_id,
            with_words("from the note"),
            "written straight to the database",
        )

    def test_a_missing_row_counts_as_empty(self, db_session: Session):
        # mirrored with empty words, so no row was created
        joplin, note_id = self.mirrored(db_session, "")
        assert words_rows(db_session) == []
        joplin.edit_note(note_id, with_words("new words"))
        refresh(db_session, joplin, note_id)
        assert [w.txt for w in words_rows(db_session)] == ["new words"]

    def test_a_missing_row_for_mirrored_words_raises(self, db_session: Session):
        joplin, note_id = self.mirrored(db_session, "mirrored words")
        (row,) = words_rows(db_session)
        db_session.delete(row)
        db_session.commit()
        with pytest.raises(WordsConflict):
            refresh(db_session, joplin, note_id)

    def test_no_previous_body_skips_the_invariant(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, with_words("in the note"))
        # a mirror row from before bodies were stored, with words that don't
        # match anything
        stale = joplin.get_note(note_id)
        stale.body = None
        db_session.add(stale)
        db_session.add(
            MyDiaryWords(
                joplin_note_id=note_id,
                note_title=DAY,
                txt="something older",
                created_at=stale.created_time,
                updated_at=stale.updated_time,
                hash="x",
            )
        )
        db_session.commit()

        refresh(db_session, joplin, note_id)
        assert [w.txt for w in words_rows(db_session)] == ["in the note"]

    def test_recreated_note_skips_the_invariant(self, db_session: Session):
        joplin, old_id = self.mirrored(db_session, "from the note")
        (row,) = words_rows(db_session)
        row.txt = "out of step"
        db_session.add(row)
        db_session.commit()

        del joplin.notes[old_id]
        new_id = joplin.add_note(DAY, with_words("re-created"))
        refresh(db_session, joplin, new_id)
        assert [w.txt for w in words_rows(db_session)] == ["re-created"]

    def test_recreated_note_with_empty_words_raises(self, db_session: Session):
        joplin, old_id = self.mirrored(db_session, "only copy")
        del joplin.notes[old_id]
        new_id = joplin.add_note(DAY, with_words(""))
        with pytest.raises(WordsConflict):
            refresh(db_session, joplin, new_id)
        db_session.expire_all()
        assert db_session.get(JoplinNote, old_id) is not None
        assert db_session.get(JoplinNote, new_id) is None


class TestSyncChangedNotes:
    def test_fetches_only_what_changed(self, db_session: Session):
        joplin = InMemoryJoplin()
        joplin.add_note("2026-09-11", "## Words\n\n#a\n")
        b = joplin.add_note("2026-09-12", "## Words\n\n#b\n")
        first = sync_changed_notes(db_session, joplin)
        assert (first.notes_checked, first.notes_synced, first.tags_added) == (2, 2, 2)

        again = sync_changed_notes(db_session, joplin)
        assert (again.notes_checked, again.notes_synced, again.tags_added) == (2, 0, 0)

        # one edited in Joplin, one new
        joplin.edit_note(b, "## Words\n\n#b #bb\n")
        joplin.add_note("2026-09-13", "## Words\n\n#c\n")
        third = sync_changed_notes(db_session, joplin)
        assert (third.notes_checked, third.notes_synced, third.tags_added) == (3, 2, 2)

    def test_force_syncs_everything(self, db_session: Session):
        joplin = InMemoryJoplin()
        joplin.add_note("2026-09-11", "#a")
        joplin.add_note("2026-09-12", "#b")
        sync_changed_notes(db_session, joplin)
        forced = sync_changed_notes(db_session, joplin, force=True)
        assert (forced.notes_checked, forced.notes_synced, forced.tags_added) == (
            2,
            2,
            0,
        )

    @pytest.mark.parametrize("missing", ["body", "sync time"])
    def test_rows_without_a_body_or_a_sync_time_are_fetched(
        self, db_session: Session, missing
    ):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note("2026-09-11", "#a")
        # a mirror row with the same updated_time, but from before bodies were
        # stored, or never synced
        stale = joplin.get_note(note_id)
        stale.time_last_api_sync = datetime(2026, 1, 1)
        if missing == "body":
            stale.body = None
            stale.body_hash = None
        else:
            stale.time_last_api_sync = None
        db_session.add(stale)
        db_session.commit()

        summary = sync_changed_notes(db_session, joplin)
        assert summary.notes_synced == 1
        assert db_session.get(JoplinNote, note_id).body == "#a"

    def test_notes_outside_the_year_folders_are_not_listed(self, db_session: Session):
        joplin = InMemoryJoplin()
        joplin.create_note("2026-09-11", "#a", joplin.notebook_id)
        assert sync_changed_notes(db_session, joplin).notes_checked == 0

    def test_a_words_conflict_is_logged_and_the_rest_sync(
        self, db_session: Session, caplog
    ):
        joplin = InMemoryJoplin()
        conflicted = joplin.add_note("2026-09-11", with_words("only copy"))
        other = joplin.add_note("2026-09-12", with_words("fine"))
        sync_changed_notes(db_session, joplin)

        joplin.edit_note(conflicted, with_words(""))
        joplin.edit_note(other, with_words("fine #edited"))
        with caplog.at_level(logging.ERROR):
            summary = sync_changed_notes(db_session, joplin)

        assert (summary.notes_checked, summary.notes_synced) == (2, 1)
        assert "2026-09-11" in caplog.text
        assert "words conflict" in caplog.text
        assert [t.key for t, _ in tags_for_target(db_session, "day", "2026-09-12")] == [
            "edited"
        ]
        db_session.expire_all()
        assert db_session.get(JoplinNote, conflicted).body == with_words("only copy")

    def test_one_day(self, db_session: Session):
        joplin = InMemoryJoplin()
        joplin.add_note("2026-09-11", "#a")
        summary = sync_one_day(db_session, joplin, datetime(2026, 9, 11))
        assert (summary.notes_checked, summary.notes_synced, summary.tags_added) == (
            1,
            1,
            1,
        )
        missing = sync_one_day(db_session, joplin, datetime(2026, 1, 1))
        assert (missing.notes_checked, missing.notes_synced) == (0, 0)


class TestJoplinNoteTags:
    """Joplin's own note-level tags, one way: Joplin -> mydiary."""

    def test_note_tags_become_joplin_links(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, WORDS)
        joplin.tag_note(note_id, "Hiking")
        joplin.tag_note(note_id, "book:The Husbands")
        assert refresh(db_session, joplin, note_id) == (
            3,
            0,
        )  # the hashtag plus two Joplin tags
        got = {
            t.key: (t.name, src) for t, src in tags_for_target(db_session, "day", DAY)
        }
        assert got == {
            "dog:ruffles": ("ruffles", "note"),
            "hiking": ("Hiking", "joplin"),
            "book:the-husbands": ("book:The Husbands", "joplin"),
        }

    def test_tag_removed_in_joplin_removes_only_its_link(self, db_session: Session):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, "no hashtags")
        joplin.tag_note(note_id, "hiking")
        joplin.tag_note(note_id, "rain")
        refresh(db_session, joplin, note_id)
        set_target_tags(db_session, "day", DAY, ["manual-one"])

        joplin.untag_note(note_id, "hiking")
        assert refresh(db_session, joplin, note_id) == (0, 1)
        assert sorted(day_tags(db_session)) == ["manual-one", "rain"]

    def test_hashtag_and_joplin_tag_with_the_same_key_share_one_link(
        self, db_session: Session
    ):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, "## Words\n\n#hiking\n")
        joplin.tag_note(note_id, "hiking")
        refresh(db_session, joplin, note_id)
        ((tag, source),) = tags_for_target(db_session, "day", DAY)
        assert (tag.key, source) == ("hiking", "note")
        # the hashtag goes, the Joplin tag stays: the link changes hands
        joplin.edit_note(note_id, "## Words\n\nnothing\n")
        refresh(db_session, joplin, note_id)
        ((tag, source),) = tags_for_target(db_session, "day", DAY)
        assert (tag.key, source) == ("hiking", "joplin")

    def test_full_sync_sees_a_tag_change_without_a_body_change(
        self, db_session: Session
    ):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(DAY, "## Words\n\nplain\n")
        sync_changed_notes(db_session, joplin)
        assert tags_for_target(db_session, "day", DAY) == []

        # tagging a note in Joplin does not touch its updated_time
        joplin.tag_note(note_id, "hiking")
        summary = sync_changed_notes(db_session, joplin)
        assert (summary.notes_synced, summary.tags_added) == (0, 1)
        assert [(t.key, s) for t, s in tags_for_target(db_session, "day", DAY)] == [
            ("hiking", "joplin")
        ]

        joplin.untag_note(note_id, "hiking")
        summary = sync_changed_notes(db_session, joplin)
        assert (summary.tags_added, summary.tags_removed) == (0, 1)
        assert tags_for_target(db_session, "day", DAY) == []

    def test_tags_on_notes_outside_the_diary_are_ignored(self, db_session: Session):
        joplin = InMemoryJoplin()
        joplin.add_note(DAY, "plain")
        elsewhere = joplin.create_note("some other note", "", joplin.notebook_id)
        joplin.tag_note(elsewhere, "hiking")
        sync_changed_notes(db_session, joplin)
        assert db_session.exec(select(TagLink)).all() == []
