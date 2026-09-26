# -*- coding: utf-8 -*-
"""The section registry's template, refresh and creation of a Diary Note."""

import json
from datetime import date
from pathlib import Path
from typing import List

import pendulum
import pytest
from sqlmodel import Session, select

from mydiary import pocket_connector
from mydiary.diary_note import DiaryNote, NoteExists, WordsConflict, new_note_body
from mydiary.markdown_edits import MarkdownDoc
from mydiary.models import GoogleCalendarEvent, JoplinNote, MyDiaryWords
from mydiary.mydiary_day import MyDiaryDay, dropped_plays
from mydiary.spotify_connector import MyDiarySpotify
from tests.in_memory_joplin import InMemoryJoplin

DT = pendulum.datetime(2024, 10, 19, tz="America/New_York")
TITLE = "2024-10-19"
PREAMBLE = "# Oct 19, 2024\n\ntimezone: America/New_York\n\n"
LEGACY_REF = "![](:/" + "9" * 32 + ")"


@pytest.fixture
def events(rootdir: str) -> List[GoogleCalendarEvent]:
    path = Path(rootdir).joinpath("mydiary_day_data", "gcal_events.json")
    return [
        GoogleCalendarEvent.from_gcal_api_event(e) for e in json.loads(path.read_text())
    ]


@pytest.fixture
def tracks(loaded_db: Session):
    return MyDiarySpotify().get_tracks_for_day(DT, session=loaded_db)


@pytest.fixture
def no_pocket(monkeypatch):
    # the template asks the app's own database for the Pocket cutoff
    monkeypatch.setattr(
        pocket_connector,
        "get_pocket_section_cutoff",
        lambda session=None: pendulum.datetime(2000, 1, 1),
    )


def make_day(joplin, events=(), tracks=(), **kwargs) -> MyDiaryDay:
    return MyDiaryDay(
        dt=DT,
        joplin_connector=joplin,
        google_calendar_events=list(events),
        spotify_tracks=list(tracks),
        **kwargs,
    )


def headings(body: str) -> List[str]:
    return [s.title for s in MarkdownDoc(body).sections if s.title]


def section_txt(body: str, heading: str) -> str:
    return MarkdownDoc(body).get_section_by_title(heading).txt


class TestNewNoteBody:
    def test_lays_sections_out_in_registry_order(self):
        body = new_note_body(
            "# preamble\n\n",
            {
                "Spotify tracks": "None",
                "Words": "",
                "Location": "a map",
                "Google Calendar events": "None",
                "Images": "",
            },
        )
        assert body == (
            "# preamble\n\n"
            "## Words\n\n"
            "## Images\n\n"
            "## Location\n\na map\n\n"
            "## Google Calendar events\n\nNone\n\n"
            "## Spotify tracks\n\nNone\n\n"
        )

    def test_leaves_out_sections_not_given(self):
        body = new_note_body("", {"Words": "hi", "Spotify tracks": "None"})
        assert headings(body) == ["Words", "Spotify tracks"]

    def test_refuses_a_heading_the_registry_lacks(self):
        with pytest.raises(ValueError):
            new_note_body("", {"Dreams": "flying"})

    def test_init_markdown_is_the_template(self, events, no_pocket):
        day = make_day(None, events, words=MyDiaryWords.from_txt("Test words."))
        assert day.init_markdown() == (
            PREAMBLE + "## Words\n\nTest words.\n\n"
            "## Images\n\n"
            "## Google Calendar events\n\n"
            "Start | End | Summary\n--- | --- | ---\n"
            f"{events[0].to_markdown()}\n{events[1].to_markdown()}\n\n"
            "## Spotify tracks\n\nNone\n\n"
        )

    def test_init_markdown_has_pocket_before_the_cutoff(self, monkeypatch):
        monkeypatch.setattr(
            pocket_connector,
            "get_pocket_section_cutoff",
            lambda session=None: pendulum.datetime(2025, 1, 1),
        )
        assert make_day(None).init_markdown() == (
            PREAMBLE + "## Words\n\n"
            "## Images\n\n"
            "## Google Calendar events\n\nNone\n\n"
            "## Pocket articles\n\nNone\n\n"
            "## Spotify tracks\n\nNone\n\n"
        )


class TestRefresh:
    def test_drops_a_cancelled_event(self, db_session: Session, events, no_pocket):
        joplin = InMemoryJoplin()
        body = make_day(joplin, events).init_markdown()
        note_id = joplin.add_note(TITLE, body)

        make_day(joplin, events[1:]).update_joplin_note(session=db_session)

        new_body = joplin.notes[note_id].body
        assert events[0].summary not in new_body
        assert events[1].summary in new_body
        assert len(joplin.updates) == 1

    def test_every_event_cancelled_leaves_none(
        self, db_session: Session, events, no_pocket
    ):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(TITLE, make_day(joplin, events).init_markdown())

        make_day(joplin).update_joplin_note(session=db_session)

        body = joplin.notes[note_id].body
        assert section_txt(body, "Google Calendar events").strip() == (
            "## Google Calendar events\n\nNone"
        )

    @pytest.mark.parametrize(
        "present, expected",
        [
            (
                ["Words", "Images", "Location", "Google Calendar events"],
                [
                    "Words",
                    "Images",
                    "Location",
                    "Google Calendar events",
                    "Spotify tracks",
                ],
            ),
            (
                ["Words", "Images", "Google Calendar events", "Pocket articles"],
                [
                    "Words",
                    "Images",
                    "Google Calendar events",
                    "Pocket articles",
                    "Spotify tracks",
                ],
            ),
            (
                ["Words", "Images", "Location", "Pocket articles", "Spotify tracks"],
                [
                    "Words",
                    "Images",
                    "Location",
                    "Google Calendar events",
                    "Pocket articles",
                    "Spotify tracks",
                ],
            ),
        ],
    )
    def test_backfills_a_missing_section_in_registry_order(
        self, loaded_db: Session, events, tracks, present, expected
    ):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(
            TITLE, new_note_body(PREAMBLE, {h: "x" for h in present})
        )

        make_day(joplin, events, tracks).update_joplin_note(session=loaded_db)

        body = joplin.notes[note_id].body
        assert headings(body) == expected
        assert events[1].summary in section_txt(body, "Google Calendar events")
        spotify = section_txt(body, "Spotify tracks")
        assert spotify.count("\n") > 3  # the header and some tracks
        assert "| --- |" in spotify

    def test_leaves_written_and_other_sections_byte_identical(
        self, loaded_db: Session, events, tracks
    ):
        joplin = InMemoryJoplin()
        body = (
            "# Oct 19, 2024\n\ntimezone: America/New_York\n\n"
            "## Words\n\nA parade,  then  pierogi.\n\n\n"
            f"## Images\n\n{LEGACY_REF}\n\nsomething typed here\n\n"
            "## Location\n\nan older map\n"
            "## Google Calendar events\n\nNone\n\n"
            "## Pocket articles\n\nNone\n\n"
            "## Spotify tracks\n\nNone\n\n"
            "## Later\n\n  kept as typed  \n"
        )
        note_id = joplin.add_note(TITLE, body)
        day = make_day(joplin, events, tracks)
        # refresh must not build a Location section: this would fail if it did
        day.owntracks_locations = ["not a location"]

        day.update_joplin_note(session=loaded_db)

        new_body = joplin.notes[note_id].body
        assert new_body != body
        assert new_body.startswith(body.split("## Google Calendar events")[0])
        for heading in ("Pocket articles", "Later"):
            assert section_txt(new_body, heading) == section_txt(body, heading)

    def test_writes_nothing_when_nothing_changed(
        self, loaded_db: Session, events, tracks
    ):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(TITLE, "## Words\n\nhi\n")
        make_day(joplin, events, tracks).update_joplin_note(session=loaded_db)
        assert len(joplin.updates) == 1

        make_day(joplin, events, tracks).update_joplin_note(session=loaded_db)

        assert len(joplin.updates) == 1
        assert loaded_db.get(JoplinNote, note_id).body == joplin.notes[note_id].body

    def test_keeps_spotify_tracks_that_would_lose_a_play(
        self, loaded_db: Session, events, tracks
    ):
        joplin = InMemoryJoplin()
        body = new_note_body(
            PREAMBLE,
            {
                "Words": "hi",
                "Google Calendar events": "None",
                "Spotify tracks": make_day(None, tracks=tracks).spotify_tracks_markdown(
                    timezone=DT.timezone
                ),
            },
        )
        note_id = joplin.add_note(TITLE, body)

        # built with other day boundaries: the first play falls on another day
        make_day(joplin, events, tracks[1:]).update_joplin_note(session=loaded_db)

        new_body = joplin.notes[note_id].body
        assert section_txt(new_body, "Spotify tracks") == section_txt(
            body, "Spotify tracks"
        )
        # the rest of the refresh still happened
        assert events[1].summary in section_txt(new_body, "Google Calendar events")

    def test_replaces_spotify_tracks_that_only_gain_plays(
        self, loaded_db: Session, tracks
    ):
        joplin = InMemoryJoplin()
        fewer = make_day(None, tracks=tracks[1:]).spotify_tracks_markdown(
            timezone=DT.timezone
        )
        note_id = joplin.add_note(
            TITLE, new_note_body(PREAMBLE, {"Words": "hi", "Spotify tracks": fewer})
        )
        day = make_day(joplin, tracks=tracks)

        day.update_joplin_note(session=loaded_db)

        assert section_txt(joplin.notes[note_id].body, "Spotify tracks").strip() == (
            "## Spotify tracks\n\n" + day.spotify_tracks_markdown(timezone=DT.timezone)
        )

    def test_dropped_plays_counts_repeats(self):
        a, b = "spotify:track:aaa", "spotify:track:bbb"
        assert dropped_plays(f"{a}\n{b}", f"{b}\n{a}\nspotify:track:ccc") == 0
        assert dropped_plays(f"{a}\n{a}\n{b}", f"{a}\n{b}") == 1
        assert dropped_plays(f"{a}\n{b}", "None") == 2
        assert dropped_plays("None", "None") == 0
        # an image someone put in the section counts too
        assert dropped_plays(f"None\n\n{LEGACY_REF}", "None") == 1

    def test_refreshes_the_mirror(self, db_session: Session, events):
        joplin = InMemoryJoplin()
        note_id = joplin.add_note(TITLE, "## Words\n\nhi\n")

        make_day(joplin, events).update_joplin_note(session=db_session)

        db_note = db_session.get(JoplinNote, note_id)
        assert db_note.body == joplin.notes[note_id].body
        assert db_note.has_words is True

    def test_raises_when_the_day_has_no_note(self, db_session: Session):
        joplin = InMemoryJoplin()
        with pytest.raises(RuntimeError, match="does not already exist"):
            make_day(joplin).update_joplin_note(session=db_session)
        assert joplin.notes == {}


class TestCreate:
    def test_creates_the_template_and_mirrors_it(
        self, db_session: Session, events, no_pocket
    ):
        joplin = InMemoryJoplin()
        day = make_day(joplin, events, words=MyDiaryWords.from_txt("Test words."))

        day.init_joplin_note(session=db_session)

        note = joplin.notes[day.joplin_note_id]
        assert note.title == TITLE
        assert joplin.folders[note.parent_id].title == "2024"
        assert note.body == day.init_markdown()
        db_note = db_session.get(JoplinNote, note.id)
        assert db_note.body == note.body
        assert db_note.has_words is True
        words = db_session.exec(
            select(MyDiaryWords).where(MyDiaryWords.joplin_note_id == note.id)
        ).one()
        assert words.txt == "Test words."

    def test_posts_a_given_body_as_is(self, db_session: Session):
        joplin = InMemoryJoplin()
        body = "anything the browser sent\n## Not a registry section\n"

        make_day(joplin).init_joplin_note(session=db_session, body=body)

        (note,) = joplin.notes.values()
        assert note.body == body
        assert db_session.get(JoplinNote, note.id).body == body

    def test_refuses_a_day_that_has_a_note(self, db_session: Session):
        joplin = InMemoryJoplin()
        joplin.add_note(TITLE, "## Words\n\nhi\n")

        with pytest.raises(NoteExists):
            DiaryNote.create(db_session, joplin, date(2024, 10, 19), "body")

        assert len(joplin.notes) == 1

    def test_refuses_a_body_that_would_lose_mirrored_words(self, db_session: Session):
        joplin = InMemoryJoplin()
        old_id = joplin.add_note(TITLE, "## Words\n\nthe only copy\n")
        DiaryNote.get(joplin, old_id).refresh_mirror(db_session)
        # deleted in the Joplin app; the mirror still has its words
        del joplin.notes[old_id]

        with pytest.raises(WordsConflict):
            DiaryNote.create(db_session, joplin, date(2024, 10, 19), "## Words\n\n")

        assert joplin.notes == {}

    def test_init_or_update_creates_then_refreshes(
        self, db_session: Session, events, no_pocket
    ):
        joplin = InMemoryJoplin()
        make_day(joplin, events[1:]).init_or_update_joplin_note(session=db_session)
        (note_id,) = joplin.notes
        assert joplin.updates == []

        make_day(joplin, events).init_or_update_joplin_note(session=db_session)

        assert len(joplin.notes) == 1
        assert events[0].summary in joplin.notes[note_id].body
        assert len(joplin.updates) == 1
