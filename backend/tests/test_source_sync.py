# -*- coding: utf-8 -*-
"""Source Sync of a day: every Source runs, and each fails on its own."""

import pendulum
from sqlmodel import Session, select

from mydiary.models import GoogleCalendarEvent, MyDiaryWords
from mydiary.source_sync import SourceStatus, sync_sources
from tests.test_gcal_refresh import FakeCalendar
from tests.test_gcal_sync import nine

DT = pendulum.datetime(2031, 3, 10, tz="America/New_York")


class FakeSpotify:
    def __init__(self, error=None):
        self.error = error
        self.sessions = []

    def save_recent_tracks_to_database(self, session=None) -> int:
        self.sessions.append(session)
        if self.error is not None:
            # half-done work the failure leaves in the session
            session.add(MyDiaryWords.from_txt(txt="pending", title="spotify"))
            raise self.error
        return 0


class FakeOwnTracks:
    def __init__(self):
        self.sessions = []

    def save_locations_to_database(self, session=None) -> int:
        self.sessions.append(session)
        session.add(MyDiaryWords.from_txt(txt="saved", title="owntracks"))
        session.commit()
        return 1


def failing_to_build(error):
    def build():
        raise error

    return build


def test_every_source_runs(db_session: Session):
    spotify, owntracks = FakeSpotify(), FakeOwnTracks()
    calendar = FakeCalendar([nine("ev1")])

    report = sync_sources(
        db_session,
        DT,
        spotify=lambda: spotify,
        gcal=lambda: calendar,
        owntracks=lambda: owntracks,
    )

    assert report.statuses == [
        SourceStatus("Spotify", ok=True),
        SourceStatus("Google Calendar", ok=True),
        SourceStatus("OwnTracks", ok=True),
    ]
    assert report.failed == []
    assert spotify.sessions == [db_session]
    assert owntracks.sessions == [db_session]
    assert calendar.fetches == 1
    assert [e.id for e in db_session.exec(select(GoogleCalendarEvent))] == ["ev1"]


def test_a_source_that_cant_be_set_up_fails_alone(db_session: Session):
    spotify, owntracks = FakeSpotify(), FakeOwnTracks()

    report = sync_sources(
        db_session,
        DT,
        spotify=lambda: spotify,
        gcal=failing_to_build(RuntimeError("token expired")),
        owntracks=lambda: owntracks,
    )

    assert report.failed == [
        SourceStatus("Google Calendar", ok=False, error="RuntimeError: token expired")
    ]
    assert spotify.sessions and owntracks.sessions


def test_a_failure_leaves_nothing_pending_for_the_next_source(db_session: Session):
    owntracks = FakeOwnTracks()

    report = sync_sources(
        db_session,
        DT,
        spotify=lambda: FakeSpotify(error=ConnectionError("unreachable")),
        gcal=lambda: FakeCalendar([]),
        owntracks=lambda: owntracks,
    )

    assert [s.source for s in report.failed] == ["Spotify"]
    titles = [w.note_title for w in db_session.exec(select(MyDiaryWords))]
    assert titles == ["owntracks"]


def test_a_failure_without_a_message_is_named(db_session: Session):
    report = sync_sources(
        db_session,
        DT,
        spotify=failing_to_build(TimeoutError()),
        gcal=lambda: FakeCalendar([]),
        owntracks=lambda: FakeOwnTracks(),
    )

    assert report.failed == [SourceStatus("Spotify", ok=False, error="TimeoutError")]


def test_google_calendar_syncs_the_requested_day(db_session: Session):
    days = []

    class RecordingCalendar(FakeCalendar):
        def get_day(self, dt):
            days.append(dt)
            return super().get_day(dt)

    sync_sources(
        db_session,
        DT,
        spotify=lambda: FakeSpotify(),
        gcal=lambda: RecordingCalendar([]),
        owntracks=lambda: FakeOwnTracks(),
    )

    assert days == [DT]
