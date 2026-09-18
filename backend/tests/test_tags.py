# -*- coding: utf-8 -*-

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from mydiary.models import Dog, JoplinNote, PerformSong, Tag, TagLink
from mydiary.tags import (
    ENTITY_KINDS,
    UnknownTargetType,
    delete_tag,
    get_or_create_tag,
    namespaces,
    resolve_tag,
    set_target_tags,
    sync_note_tags,
    tag_by_key,
    tag_link_counts,
    tag_targets,
    tags_for_target,
    tags_for_targets,
)


def make_note(title: str, body: str, note_id: str = None) -> JoplinNote:
    ts = datetime(2026, 9, 13, 12, 0, 0)
    return JoplinNote(
        id=note_id or f"note-{title}",
        parent_id="folder",
        title=title,
        body=body,
        created_time=ts,
        updated_time=ts,
    )


def links(session: Session, **where):
    stmt = select(TagLink)
    for k, v in where.items():
        stmt = stmt.where(getattr(TagLink, k) == v)
    return session.exec(stmt).all()


class TestTagModel:
    def test_bare_tag_has_empty_namespace_and_key_is_slug(self, db_session: Session):
        tag = Tag(slug="hiking", name="hiking")
        db_session.add(tag)
        db_session.commit()
        assert tag.namespace == ""
        assert tag.key == "hiking"

    def test_namespaced_key(self):
        assert Tag(namespace="dog", slug="ruffles", name="Ruffles").key == "dog:ruffles"

    def test_namespace_slug_is_unique(self, db_session: Session):
        db_session.add(Tag(namespace="dog", slug="ruffles", name="a"))
        db_session.commit()
        db_session.add(Tag(namespace="dog", slug="ruffles", name="b"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_same_slug_in_different_namespaces_is_fine(self, db_session: Session):
        db_session.add(Tag(namespace="dog", slug="ruffles", name="a"))
        db_session.add(Tag(namespace="", slug="ruffles", name="b"))
        db_session.commit()
        assert len(db_session.exec(select(Tag)).all()) == 2


class TestGetOrCreate:
    def test_idempotent(self, db_session: Session):
        a = get_or_create_tag(db_session, "dog", "ruffles")
        b = get_or_create_tag(db_session, "dog", "ruffles")
        assert a.id == b.id
        assert len(db_session.exec(select(Tag)).all()) == 1

    def test_name_defaults_to_slug_and_is_kept_on_repeat(self, db_session: Session):
        a = get_or_create_tag(db_session, "", "saved-for-later", name="saved for later")
        b = get_or_create_tag(db_session, "", "saved-for-later", name="ignored")
        assert a.name == "saved for later"
        assert b.name == "saved for later"
        assert get_or_create_tag(db_session, "", "hiking").name == "hiking"

    def test_tag_by_key(self, db_session: Session):
        made = get_or_create_tag(db_session, "dog", "ruffles")
        assert tag_by_key(db_session, "dog:ruffles").id == made.id
        assert tag_by_key(db_session, "Dog:Ruffles").id == made.id
        assert tag_by_key(db_session, "cat:ruffles") is None


class TestSyncNoteTags:
    def test_creates_note_links_for_the_day(self, db_session: Session):
        note = make_note("2026-09-13", "Walked #dog:Ruffles, went #hiking.")
        added, removed = sync_note_tags(db_session, note)
        assert (added, removed) == (2, 0)
        day_links = links(db_session, target_type="day", target_id="2026-09-13")
        assert {l.source for l in day_links} == {"note"}
        assert sorted(t.key for t, _ in tags_for_target(db_session, "day", "2026-09-13")) == [
            "dog:ruffles",
            "hiking",
        ]

    def test_second_sync_changes_nothing(self, db_session: Session):
        note = make_note("2026-09-13", "#hiking")
        sync_note_tags(db_session, note)
        assert sync_note_tags(db_session, note) == (0, 0)
        assert len(links(db_session)) == 1

    def test_removed_hashtag_removes_only_its_note_link(self, db_session: Session):
        note = make_note("2026-09-13", "#hiking #rain")
        sync_note_tags(db_session, note)
        set_target_tags(db_session, "day", "2026-09-13", ["manual-one"])
        note.body = "#rain"
        assert sync_note_tags(db_session, note) == (0, 1)
        assert sorted(t.key for t, _ in tags_for_target(db_session, "day", "2026-09-13")) == [
            "manual-one",
            "rain",
        ]

    def test_existing_manual_link_is_left_alone(self, db_session: Session):
        set_target_tags(db_session, "day", "2026-09-13", ["hiking"])
        note = make_note("2026-09-13", "#hiking")
        assert sync_note_tags(db_session, note) == (0, 0)
        (link,) = links(db_session, target_id="2026-09-13")
        assert link.source == "manual"
        # and dropping the hashtag later does not take the manual link with it
        note.body = "nothing here"
        assert sync_note_tags(db_session, note) == (0, 0)
        assert len(links(db_session, target_id="2026-09-13")) == 1

    def test_empty_body(self, db_session: Session):
        note = make_note("2026-09-13", None)
        assert sync_note_tags(db_session, note) == (0, 0)

    def test_tags_of_other_days_are_untouched(self, db_session: Session):
        sync_note_tags(db_session, make_note("2026-09-12", "#hiking"))
        sync_note_tags(db_session, make_note("2026-09-13", "#rain"))
        assert len(links(db_session, target_id="2026-09-12")) == 1
        assert len(links(db_session, target_id="2026-09-13")) == 1


class TestSetTargetTags:
    def test_sets_and_replaces(self, db_session: Session):
        tags = set_target_tags(db_session, "song", "7", ["Rock", "dog:Ruffles"])
        assert sorted(t.key for t in tags) == ["dog:ruffles", "rock"]
        set_target_tags(db_session, "song", "7", ["rock", "new"])
        assert sorted(t.key for t, _ in tags_for_target(db_session, "song", "7")) == [
            "new",
            "rock",
        ]
        assert {l.source for l in links(db_session, target_id="7")} == {"manual"}

    def test_empty_list_clears_manual_links(self, db_session: Session):
        set_target_tags(db_session, "song", "7", ["rock"])
        assert set_target_tags(db_session, "song", "7", []) == []
        assert links(db_session, target_id="7") == []

    def test_note_links_are_neither_removed_nor_duplicated(self, db_session: Session):
        sync_note_tags(db_session, make_note("2026-09-13", "#hiking"))
        set_target_tags(db_session, "day", "2026-09-13", ["hiking", "extra"])
        day_links = links(db_session, target_id="2026-09-13")
        assert len(day_links) == 2
        by_key = {tag_by_key(db_session, k).id: k for k in ["hiking", "extra"]}
        sources = {by_key[l.tag_id]: l.source for l in day_links}
        assert sources == {"hiking": "note", "extra": "manual"}
        # removing it from the manual set leaves the note link
        set_target_tags(db_session, "day", "2026-09-13", [])
        assert [l.source for l in links(db_session, target_id="2026-09-13")] == ["note"]

    def test_source_is_recorded(self, db_session: Session):
        set_target_tags(db_session, "article", "123", ["news"], source="pocket")
        (link,) = links(db_session, target_id="123")
        assert link.source == "pocket"

    def test_unknown_target_type(self, db_session: Session):
        with pytest.raises(UnknownTargetType):
            set_target_tags(db_session, "unicorn", "1", ["x"])
        with pytest.raises(UnknownTargetType):
            tags_for_target(db_session, "unicorn", "1")

    def test_unparseable_key_is_rejected(self, db_session: Session):
        with pytest.raises(ValueError):
            set_target_tags(db_session, "song", "7", ["!!!"])


class TestLookups:
    def test_tags_for_targets_is_batched_by_id(self, db_session: Session):
        set_target_tags(db_session, "article", "1", ["a", "b"])
        set_target_tags(db_session, "article", "2", ["b"])
        got = tags_for_targets(db_session, "article", ["1", "2", "3"])
        assert sorted(t.key for t in got["1"]) == ["a", "b"]
        assert [t.key for t in got["2"]] == ["b"]
        assert got["3"] == []

    def test_link_counts_and_namespaces(self, db_session: Session):
        set_target_tags(db_session, "article", "1", ["a", "dog:x"])
        set_target_tags(db_session, "article", "2", ["a"])
        get_or_create_tag(db_session, "book", "lonely")
        counts = tag_link_counts(db_session)
        assert counts[tag_by_key(db_session, "a").id] == 2
        assert counts[tag_by_key(db_session, "dog:x").id] == 1
        assert tag_by_key(db_session, "book:lonely").id not in counts
        assert namespaces(db_session) == [
            ("", 1),
            ("article", 0),
            ("book", 1),
            ("day", 0),
            ("dog", 1),
            ("recipe", 0),
            ("song", 0),
        ]

    def test_delete_tag_removes_links(self, db_session: Session):
        set_target_tags(db_session, "article", "1", ["a", "b"])
        delete_tag(db_session, tag_by_key(db_session, "a"))
        assert tag_by_key(db_session, "a") is None
        assert [t.key for t, _ in tags_for_target(db_session, "article", "1")] == ["b"]


class TestResolution:
    def test_registry_shape(self):
        assert set(ENTITY_KINDS) >= {"day", "dog", "recipe", "song", "article"}
        assert ENTITY_KINDS["article"].resolve is None
        assert ENTITY_KINDS["song"].frontend_route == "performSong"

    def test_dog_resolves_by_slugified_name(self, db_session: Session):
        dog = Dog(name="Ruffles")
        db_session.add(dog)
        db_session.commit()
        ref = resolve_tag(db_session, get_or_create_tag(db_session, "dog", "ruffles"))
        assert ref is not None
        assert (ref.kind, ref.id, ref.label) == ("dog", str(dog.id), "Ruffles")

    def test_no_row_and_ambiguous_rows_do_not_resolve(self, db_session: Session):
        tag = get_or_create_tag(db_session, "dog", "ruffles")
        assert resolve_tag(db_session, tag) is None
        db_session.add(Dog(name="Ruffles"))
        db_session.add(Dog(name="ruffles"))
        db_session.commit()
        assert resolve_tag(db_session, tag) is None

    def test_unregistered_namespace_and_bare_tag_do_not_resolve(self, db_session: Session):
        assert resolve_tag(db_session, get_or_create_tag(db_session, "book", "x")) is None
        assert resolve_tag(db_session, get_or_create_tag(db_session, "", "x")) is None

    def test_song_resolves_with_a_route(self, db_session: Session):
        song = PerformSong(name="Wonderwall", artist_name="Oasis")
        db_session.add(song)
        db_session.commit()
        ref = resolve_tag(db_session, get_or_create_tag(db_session, "song", "wonderwall"))
        assert (ref.id, ref.label, ref.frontend_route) == (
            str(song.id),
            "Wonderwall",
            "performSong",
        )

    def test_day_resolves_to_a_note_by_title(self, db_session: Session):
        db_session.add(make_note("2026-09-13", ""))
        db_session.commit()
        ref = resolve_tag(db_session, get_or_create_tag(db_session, "day", "2026-09-13"))
        assert (ref.kind, ref.id, ref.frontend_route) == ("day", "2026-09-13", "MyDiaryDay")
        assert resolve_tag(db_session, get_or_create_tag(db_session, "day", "2026-01-01")) is None


class TestTagTargets:
    def test_hydrates_every_kind_and_skips_missing_rows(self, db_session: Session):
        song = PerformSong(name="Wonderwall")
        db_session.add(song)
        db_session.add(make_note("2026-09-13", "#hiking"))
        db_session.commit()
        sync_note_tags(db_session, db_session.exec(select(JoplinNote)).one())
        set_target_tags(db_session, "song", str(song.id), ["hiking"])
        set_target_tags(db_session, "song", "9999", ["hiking"])  # no such song

        refs = tag_targets(db_session, tag_by_key(db_session, "hiking"))
        assert [(r.kind, r.id, r.label, r.source) for r in refs] == [
            ("day", "2026-09-13", "2026-09-13", "note"),
            ("song", str(song.id), "Wonderwall", "manual"),
        ]
        assert refs[1].frontend_route == "performSong"

    def test_days_are_newest_first_and_need_no_note_row(self, db_session: Session):
        set_target_tags(db_session, "day", "2026-09-01", ["hiking"])
        set_target_tags(db_session, "day", "2026-09-13", ["hiking"])
        refs = tag_targets(db_session, tag_by_key(db_session, "hiking"))
        assert [r.id for r in refs] == ["2026-09-13", "2026-09-01"]
