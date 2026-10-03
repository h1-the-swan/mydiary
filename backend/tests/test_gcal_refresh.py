# -*- coding: utf-8 -*-
"""A Refresh of the Google Calendar events section, and its Refresh Preview."""

from typing import List, Optional

import pendulum
import pytest
from sqlmodel import Session, select

from mydiary.diary_note import new_note_body, section_content
from mydiary.gcal_refresh import (
    DiffLine,
    GcalSectionChanged,
    NoDiaryNote,
    SectionUnreadable,
    apply_gcal_refresh,
    line_diff,
    preview_gcal_refresh,
)
from mydiary.markdown_edits import MarkdownDoc
from mydiary.models import GoogleCalendarEvent
from mydiary.mydiary_day import google_calendar_events_markdown
from tests.in_memory_joplin import InMemoryJoplin

DT = pendulum.datetime(2024, 10, 19, tz="America/New_York")
TITLE = "2024-10-19"
PREAMBLE = "# Oct 19, 2024\n\ntimezone: America/New_York\n\n"


def event(event_id: str, summary: str, hour: int) -> GoogleCalendarEvent:
    start = DT.add(hours=hour)
    return GoogleCalendarEvent(
        id=event_id,
        summary=summary,
        start=start,
        end=start.add(hours=1),
        start_timezone=start.timezone_name,
        end_timezone=start.timezone_name,
    )


def made_up_events() -> List[GoogleCalendarEvent]:
    return [event("ev1", "Practice scales", 9), event("ev2", "Water the ferns", 14)]


class FakeCalendar:
    """`MyDiaryGCal` without Google: returns `events`, records saves, and
    notes what the note held when the save happened."""

    def __init__(
        self,
        events: List[GoogleCalendarEvent],
        joplin: Optional[InMemoryJoplin] = None,
        note_id: Optional[str] = None,
    ) -> None:
        self.events = events
        self.joplin = joplin
        self.note_id = note_id
        self.fetches = 0
        self.saved: List[List[GoogleCalendarEvent]] = []
        self.body_at_save: Optional[str] = None

    def get_events_for_day(self, dt) -> List[GoogleCalendarEvent]:
        self.fetches += 1
        # fresh copies, as Google would give each time
        return [e.model_copy() for e in self.events]

    def save_events_to_database(self, events, session=None) -> None:
        if self.joplin is not None:
            self.body_at_save = self.joplin.notes[self.note_id].body
        self.saved.append(events)
        for e in events:
            session.merge(e)
        session.commit()


def note_body(calendar: str) -> str:
    return new_note_body(
        PREAMBLE,
        {
            "Words": "Dear diary, a quiet day.",
            "Images": "",
            "Google Calendar events": calendar,
            "Spotify tracks": "None",
        },
    )


def sections(body: str) -> dict:
    return {s.title: s.get_content() for s in MarkdownDoc(body).sections}


@pytest.fixture
def joplin() -> InMemoryJoplin:
    return InMemoryJoplin()


@pytest.fixture
def stale_note(joplin) -> str:
    """A note whose calendar section has only the first event."""
    return joplin.add_note(
        TITLE, note_body(google_calendar_events_markdown(made_up_events()[:1]))
    )


class TestLineDiff:
    def test_marks_kept_removed_and_added_lines(self):
        assert line_diff("a\nb\nc", "a\nB\nc\nd") == [
            DiffLine("same", "a"),
            DiffLine("remove", "b"),
            DiffLine("add", "B"),
            DiffLine("same", "c"),
            DiffLine("add", "d"),
        ]

    def test_from_nothing_is_all_additions(self):
        assert line_diff("", "x\ny") == [DiffLine("add", "x"), DiffLine("add", "y")]

    def test_identical_is_all_same(self):
        assert [d.op for d in line_diff("x\ny", "x\ny")] == ["same", "same"]


class TestPreview:
    def test_shows_the_new_event(self, joplin, stale_note):
        preview = preview_gcal_refresh(joplin, DT, FakeCalendar(made_up_events()))

        assert preview.changed
        assert preview.before == google_calendar_events_markdown(made_up_events()[:1])
        assert preview.after == google_calendar_events_markdown(made_up_events())
        added = [d.text for d in preview.diff if d.op == "add"]
        assert added == [made_up_events()[1].to_markdown()]
        assert not [d for d in preview.diff if d.op == "remove"]

    def test_unchanged_day(self, joplin):
        joplin.add_note(
            TITLE, note_body(google_calendar_events_markdown(made_up_events()))
        )

        preview = preview_gcal_refresh(joplin, DT, FakeCalendar(made_up_events()))

        assert not preview.changed
        assert all(d.op == "same" for d in preview.diff)

    def test_note_without_the_section(self, joplin):
        joplin.add_note(TITLE, new_note_body(PREAMBLE, {"Words": "hi"}))

        preview = preview_gcal_refresh(joplin, DT, FakeCalendar([]))

        assert preview.before == ""
        assert preview.after == "None"

    def test_writes_nothing(self, joplin, stale_note, db_session: Session):
        gcal = FakeCalendar(made_up_events())

        preview_gcal_refresh(joplin, DT, gcal)

        assert joplin.updates == []
        assert gcal.saved == []
        assert db_session.exec(select(GoogleCalendarEvent)).all() == []

    def test_day_without_a_note(self, joplin):
        with pytest.raises(NoDiaryNote):
            preview_gcal_refresh(joplin, DT, FakeCalendar(made_up_events()))


class TestApply:
    def test_writes_after_and_nothing_else(
        self, joplin, stale_note, db_session: Session
    ):
        old_body = joplin.notes[stale_note].body
        gcal = FakeCalendar(made_up_events(), joplin, stale_note)
        preview = preview_gcal_refresh(joplin, DT, gcal)

        wrote = apply_gcal_refresh(
            db_session, joplin, DT, preview.before, preview.after, gcal
        )

        assert wrote
        new_body = joplin.notes[stale_note].body
        assert section_content(new_body, "Google Calendar events") == preview.after
        old, new = sections(old_body), sections(new_body)
        del old["Google Calendar events"], new["Google Calendar events"]
        assert new == old
        assert len(joplin.updates) == 1

    def test_saves_events_only_after_the_write(
        self, joplin, stale_note, db_session: Session
    ):
        gcal = FakeCalendar(made_up_events(), joplin, stale_note)
        preview = preview_gcal_refresh(joplin, DT, gcal)

        apply_gcal_refresh(db_session, joplin, DT, preview.before, preview.after, gcal)

        assert len(gcal.saved) == 1
        # the note already held `after` when the events were saved
        assert section_content(gcal.body_at_save, "Google Calendar events") == (
            preview.after
        )
        ids = {e.id for e in db_session.exec(select(GoogleCalendarEvent))}
        assert ids == {"ev1", "ev2"}

    def test_unchanged_writes_nothing_to_the_note(self, joplin, db_session: Session):
        md = google_calendar_events_markdown(made_up_events())
        joplin.add_note(TITLE, note_body(md))

        wrote = apply_gcal_refresh(
            db_session, joplin, DT, md, md, FakeCalendar(made_up_events())
        )

        assert not wrote
        assert joplin.updates == []

    def test_calendar_changed_since_the_preview(
        self, joplin, stale_note, db_session: Session
    ):
        gcal = FakeCalendar(made_up_events())
        preview = preview_gcal_refresh(joplin, DT, gcal)
        gcal.events = gcal.events + [event("ev3", "Call the plumber", 17)]

        with pytest.raises(GcalSectionChanged) as exc_info:
            apply_gcal_refresh(
                db_session, joplin, DT, preview.before, preview.after, gcal
            )

        assert exc_info.value.side == "calendar"
        assert joplin.updates == []
        assert gcal.saved == []

    def test_note_changed_since_the_preview(
        self, joplin, stale_note, db_session: Session
    ):
        gcal = FakeCalendar(made_up_events())
        preview = preview_gcal_refresh(joplin, DT, gcal)
        hand_edited = preview.before + "\n09:30:00 | 09:45:00 | Feed the cat"
        joplin.edit_note(stale_note, note_body(hand_edited))

        with pytest.raises(GcalSectionChanged) as exc_info:
            apply_gcal_refresh(
                db_session, joplin, DT, preview.before, preview.after, gcal
            )

        assert exc_info.value.side == "note"
        assert joplin.updates == []
        assert "Feed the cat" in joplin.notes[stale_note].body
        assert gcal.saved == []
        assert db_session.exec(select(GoogleCalendarEvent)).all() == []

    def test_day_without_a_note(self, joplin, db_session: Session):
        gcal = FakeCalendar(made_up_events())
        with pytest.raises(NoDiaryNote):
            apply_gcal_refresh(db_session, joplin, DT, "", "None", gcal)
        assert gcal.saved == []

    def test_adds_a_missing_section_in_registry_order(
        self, joplin, db_session: Session
    ):
        note_id = joplin.add_note(
            TITLE,
            new_note_body(PREAMBLE, {"Words": "hi", "Spotify tracks": "None"}),
        )
        gcal = FakeCalendar(made_up_events())
        preview = preview_gcal_refresh(joplin, DT, gcal)

        apply_gcal_refresh(db_session, joplin, DT, preview.before, preview.after, gcal)

        body = joplin.notes[note_id].body
        assert [s.title for s in MarkdownDoc(body).sections if s.title] == [
            "Words",
            "Google Calendar events",
            "Spotify tracks",
        ]
        assert section_content(body, "Words") == "hi"
        assert section_content(body, "Google Calendar events") == preview.after


class TestAwkwardNotes:
    def test_title_ending_in_a_space_is_up_to_date_once_written(
        self, joplin, db_session: Session
    ):
        joplin.add_note(TITLE, note_body("None"))
        gcal = FakeCalendar([event("ev1", "Lunch ", 12)])
        preview = preview_gcal_refresh(joplin, DT, gcal)
        apply_gcal_refresh(db_session, joplin, DT, preview.before, preview.after, gcal)

        assert not preview_gcal_refresh(joplin, DT, gcal).changed

    def test_crlf_note_is_up_to_date(self, joplin):
        md = google_calendar_events_markdown(made_up_events())
        joplin.add_note(TITLE, note_body(md).replace("\n", "\r\n"))

        assert not preview_gcal_refresh(
            joplin, DT, FakeCalendar(made_up_events())
        ).changed

    @pytest.mark.parametrize(
        "body",
        [
            note_body("None") + "## google calendar events\n\nNone\n",
            note_body("None") + "## Notes\n\n```\nunclosed\n",
        ],
        ids=["heading-twice", "open-fence"],
    )
    def test_unreadable_section(self, joplin, db_session: Session, body):
        note_id = joplin.add_note(TITLE, body)
        gcal = FakeCalendar(made_up_events())

        with pytest.raises(SectionUnreadable):
            preview_gcal_refresh(joplin, DT, gcal)
        with pytest.raises(SectionUnreadable):
            apply_gcal_refresh(
                db_session,
                joplin,
                DT,
                "",
                google_calendar_events_markdown(made_up_events()),
                gcal,
            )
        assert joplin.notes[note_id].body == body
        assert gcal.saved == []


def test_a_failed_save_still_reports_the_write(joplin, stale_note, db_session):
    gcal = FakeCalendar(made_up_events())
    preview = preview_gcal_refresh(joplin, DT, gcal)

    def broken_save(events, session=None):
        raise RuntimeError("database is locked")

    gcal.save_events_to_database = broken_save

    assert apply_gcal_refresh(
        db_session, joplin, DT, preview.before, preview.after, gcal
    )
    assert (
        section_content(joplin.notes[stale_note].body, "Google Calendar events")
        == preview.after
    )
