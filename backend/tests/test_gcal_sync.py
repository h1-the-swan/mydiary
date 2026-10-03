# -*- coding: utf-8 -*-
"""Google Calendar's Source Sync (`save_calendar_day`), the database read of
a day's events (`events_for_day`), and how `MyDiaryGCal` reads Google's
answers. All events are made up."""

from typing import List

import httplib2
import pendulum
import pytest
from googleapiclient.errors import HttpError
from sqlmodel import Session, select

from mydiary.googlecalendar_connector import (
    CalendarDay,
    MyDiaryGCal,
    events_for_day,
    save_calendar_day,
)
from mydiary.models import GoogleCalendarEvent
from tests.test_gcal_refresh import FakeCalendar

DT = pendulum.datetime(2031, 3, 10, tz="America/New_York")


def timed(
    event_id: str, start: str, end: str, tz: str, **fields
) -> GoogleCalendarEvent:
    start_dt = pendulum.parse(start, tz=tz)
    end_dt = pendulum.parse(end, tz=tz)
    return GoogleCalendarEvent(
        id=event_id,
        summary=fields.pop("summary", event_id),
        start=start_dt,
        end=end_dt,
        start_timezone=tz,
        end_timezone=tz,
        **fields,
    )


def all_day(event_id: str, first: str, end: str, stored_tz: str) -> GoogleCalendarEvent:
    """As `from_gcal_api_event` stores an all-day event: UTC midnight, shown
    in the zone the process happened to run in."""
    start_dt = pendulum.parse(first, tz="UTC").in_timezone(stored_tz)
    end_dt = pendulum.parse(end, tz="UTC").in_timezone(stored_tz)
    return GoogleCalendarEvent(
        id=event_id,
        summary=event_id,
        start=start_dt,
        end=end_dt,
        start_timezone=stored_tz,
        end_timezone=stored_tz,
    )


def store(session: Session, *events: GoogleCalendarEvent) -> None:
    for e in events:
        session.add(e)
    session.commit()


def ids(events: List[GoogleCalendarEvent]) -> List[str]:
    return [e.id for e in events]


class TestEventsForDay:
    def test_timed_events_overlapping_the_day_in_its_zone(self, db_session):
        store(
            db_session,
            timed(
                "morning", "2031-03-10T09:00", "2031-03-10T10:00", "America/New_York"
            ),
            # 23:30 in Los Angeles is 02:30 the next day in New York
            timed(
                "late-west",
                "2031-03-09T23:30",
                "2031-03-10T00:30",
                "America/Los_Angeles",
            ),
            timed(
                "over-midnight",
                "2031-03-09T23:00",
                "2031-03-10T01:00",
                "America/New_York",
            ),
            timed(
                "day-before", "2031-03-09T20:00", "2031-03-09T21:00", "America/New_York"
            ),
            timed(
                "ends-at-start",
                "2031-03-09T23:00",
                "2031-03-10T00:00",
                "America/New_York",
            ),
            timed(
                "starts-at-end",
                "2031-03-11T00:00",
                "2031-03-11T01:00",
                "America/New_York",
            ),
            # 08:00 in Rome is 03:00 in New York, the same day
            timed("rome", "2031-03-10T08:00", "2031-03-10T09:00", "Europe/Rome"),
            # 04:00-05:00 in Rome is 23:00-00:00 the day before in New York
            timed("rome-early", "2031-03-10T04:00", "2031-03-10T05:00", "Europe/Rome"),
        )

        assert ids(events_for_day(db_session, DT)) == [
            "over-midnight",
            "late-west",
            "rome",
            "morning",
        ]

    @pytest.mark.parametrize(
        "stored_tz", ["Etc/UTC", "UTC", "America/Los_Angeles", "America/New_York"]
    )
    def test_all_day_events_by_date_whatever_zone_they_were_stored_in(
        self, db_session, stored_tz
    ):
        store(
            db_session,
            all_day("this-day", "2031-03-10", "2031-03-11", stored_tz),
            all_day("day-before", "2031-03-09", "2031-03-10", stored_tz),
            all_day("day-after", "2031-03-11", "2031-03-12", stored_tz),
            all_day("three-days", "2031-03-09", "2031-03-12", stored_tz),
        )

        assert sorted(ids(events_for_day(db_session, DT))) == ["this-day", "three-days"]

    def test_all_day_in_a_day_far_from_utc(self, db_session):
        store(db_session, all_day("this-day", "2031-03-10", "2031-03-11", "UTC"))
        auckland = pendulum.datetime(2031, 3, 10, tz="Pacific/Auckland")
        honolulu = pendulum.datetime(2031, 3, 10, tz="Pacific/Honolulu")

        assert ids(events_for_day(db_session, auckland)) == ["this-day"]
        assert ids(events_for_day(db_session, honolulu)) == ["this-day"]

    def test_a_zero_length_event_at_utc_midnight_is_timed(self, db_session):
        # 20:00 in New York is UTC midnight
        store(
            db_session,
            timed(
                "reminder", "2031-03-10T20:00", "2031-03-10T20:00", "America/New_York"
            ),
        )

        assert ids(events_for_day(db_session, DT)) == ["reminder"]

    def test_the_day_clocks_go_forward(self, db_session):
        # 2031-03-09 has 23 hours in New York
        store(
            db_session,
            timed("late", "2031-03-09T23:30", "2031-03-10T00:15", "America/New_York"),
            timed("next", "2031-03-10T00:00", "2031-03-10T00:30", "America/New_York"),
        )
        day = pendulum.datetime(2031, 3, 9, tz="America/New_York")

        assert ids(events_for_day(db_session, day)) == ["late"]

    def test_all_day_events_sort_at_the_start_of_the_day(self, db_session):
        store(
            db_session,
            timed(
                "from-last-night",
                "2031-03-09T22:00",
                "2031-03-10T02:00",
                "America/New_York",
            ),
            all_day("holiday", "2031-03-10", "2031-03-11", "America/New_York"),
        )

        assert ids(events_for_day(db_session, DT)) == ["from-last-night", "holiday"]
        rome = pendulum.datetime(2031, 3, 10, tz="Europe/Rome")
        store(
            db_session,
            timed("early", "2031-03-10T00:30", "2031-03-10T00:45", "Europe/Rome"),
        )
        assert ids(events_for_day(db_session, rome))[:2] == ["holiday", "early"]

    def test_leaves_out_cancelled_and_keeps_tentative(self, db_session):
        store(
            db_session,
            timed(
                "off",
                "2031-03-10T09:00",
                "2031-03-10T10:00",
                "America/New_York",
                status="cancelled",
            ),
            timed(
                "maybe",
                "2031-03-10T11:00",
                "2031-03-10T12:00",
                "America/New_York",
                status="tentative",
            ),
        )

        assert ids(events_for_day(db_session, DT)) == ["maybe"]

    def test_writes_nothing(self, db_session):
        store(
            db_session,
            timed("a", "2031-03-10T09:00", "2031-03-10T10:00", "America/New_York"),
        )

        events_for_day(db_session, DT)

        assert not db_session.dirty and not db_session.new


def nine(event_id: str = "ev1", **fields) -> GoogleCalendarEvent:
    return timed(
        event_id, "2031-03-10T09:00", "2031-03-10T10:00", "America/New_York", **fields
    )


def rows(session: Session) -> dict:
    session.expire_all()
    return {e.id: e for e in session.exec(select(GoogleCalendarEvent))}


class TestSaveCalendarDay:
    def test_saves_the_listed_events(self, db_session):
        gcal = FakeCalendar([nine("ev1"), nine("ev2", status="tentative")])

        save_calendar_day(db_session, DT, gcal.get_day(DT), gcal)

        saved = rows(db_session)
        assert set(saved) == {"ev1", "ev2"}
        assert saved["ev2"].status == "tentative"
        assert gcal.lookups == []

    def test_updates_a_listed_event_in_place(self, db_session):
        store(db_session, nine("ev1", summary="Old title"))
        gcal = FakeCalendar([nine("ev1", summary="New title")])

        save_calendar_day(db_session, DT, gcal.get_day(DT), gcal)

        assert rows(db_session)["ev1"].summary == "New title"

    def test_marks_a_listed_cancellation(self, db_session):
        store(db_session, nine("ev1"))
        gcal = FakeCalendar([], cancelled_ids={"ev1", "never-stored"})

        save_calendar_day(db_session, DT, gcal.get_day(DT), gcal)

        saved = rows(db_session)
        assert saved["ev1"].status == "cancelled"
        # nothing to mark, and a bare id is not enough to store
        assert "never-stored" not in saved
        assert gcal.lookups == []

    def test_a_row_google_left_out_that_moved_takes_the_new_times(self, db_session):
        store(db_session, nine("ev1"))
        moved = timed("ev1", "2031-03-12T15:00", "2031-03-12T16:00", "America/New_York")
        gcal = FakeCalendar([], by_id={"ev1": moved})

        save_calendar_day(db_session, DT, gcal.get_day(DT), gcal)

        row = rows(db_session)["ev1"]
        assert gcal.lookups == ["ev1"]
        assert row.status == "confirmed"
        assert row.start == moved.start and row.end == moved.end
        assert events_for_day(db_session, DT) == []

    def test_a_row_google_left_out_that_is_gone_is_marked_cancelled(self, db_session):
        store(db_session, nine("ev1"), nine("ev2"))
        gcal = FakeCalendar([nine("ev2")], by_id={"ev1": None})

        save_calendar_day(db_session, DT, gcal.get_day(DT), gcal)

        saved = rows(db_session)
        assert gcal.lookups == ["ev1"]
        assert saved["ev1"].status == "cancelled"
        assert saved["ev2"].status == "confirmed"

    def test_rows_on_other_days_are_not_looked_up(self, db_session):
        store(
            db_session,
            timed("other", "2031-03-12T09:00", "2031-03-12T10:00", "America/New_York"),
        )
        gcal = FakeCalendar([])

        save_calendar_day(db_session, DT, gcal.get_day(DT), gcal)

        assert gcal.lookups == []
        assert rows(db_session)["other"].status == "confirmed"

    def test_a_failed_lookup_writes_nothing(self, db_session):
        store(db_session, nine("ev1"), nine("ev3"))
        # Google lists ev2 and cancels ev1, leaves out ev3, and then fails
        # to look ev3 up
        gcal = FakeCalendar([nine("ev2")], cancelled_ids={"ev1"}, by_id={})

        with pytest.raises(KeyError):
            save_calendar_day(db_session, DT, gcal.get_day(DT), gcal)

        assert not (db_session.new or db_session.dirty or db_session.deleted)
        db_session.rollback()
        saved = rows(db_session)
        assert set(saved) == {"ev1", "ev3"}
        assert saved["ev1"].status == "confirmed"


class FakeRequest:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def execute(self):
        if self.error is not None:
            raise self.error
        return self.result


class FakeEvents:
    """`service.events()`: answers `list` with `items` and `get` from
    `by_id`, recording the arguments."""

    def __init__(self, items=None, by_id=None):
        self.items = items or []
        self.by_id = by_id or {}
        self.list_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        # two pages, to check they are both read
        if kwargs["pageToken"] is None and len(self.items) > 1:
            return FakeRequest({"items": self.items[:1], "nextPageToken": "p2"})
        start = 1 if kwargs["pageToken"] == "p2" else 0
        return FakeRequest({"items": self.items[start:]})

    def get(self, calendarId, eventId):
        found = self.by_id[eventId]
        if isinstance(found, int):
            return FakeRequest(
                error=HttpError(httplib2.Response({"status": found}), b"")
            )
        return FakeRequest(found)


class FakeService:
    def __init__(self, events: FakeEvents):
        self._events = events

    def events(self):
        return self._events


def api_item(event_id: str, status: str = "confirmed", **fields) -> dict:
    item = {
        "id": event_id,
        "status": status,
        "summary": "Made-up event",
        "start": {
            "dateTime": "2031-03-10T09:00:00-04:00",
            "timeZone": "America/New_York",
        },
        "end": {
            "dateTime": "2031-03-10T10:00:00-04:00",
            "timeZone": "America/New_York",
        },
    }
    item.update(fields)
    return item


class TestMyDiaryGCal:
    def test_get_day_lists_cancelled_events_apart(self):
        events = FakeEvents(
            items=[
                api_item("ev1"),
                # a cancelled instance of a recurring event comes with times
                api_item(
                    "series_20310310T130000Z", "cancelled", recurringEventId="series"
                ),
                # Google only promises id and status on a cancelled event
                {"id": "bare", "status": "cancelled"},
                api_item("ev2", "tentative"),
            ]
        )
        gcal = MyDiaryGCal(service=FakeService(events))

        day = gcal.get_day(DT)

        assert ids(day.events) == ["ev1", "ev2"]
        assert day.events[1].status == "tentative"
        assert day.cancelled_ids == {"series_20310310T130000Z", "bare"}
        assert events.list_kwargs["showDeleted"] is True
        assert events.list_kwargs["singleEvents"] is True
        assert events.list_kwargs["timeMin"] == "2031-03-10T00:00:00-04:00"
        assert events.list_kwargs["timeMax"] == "2031-03-11T00:00:00-04:00"

    def test_get_event(self):
        moved = api_item(
            "moved",
            start={
                "dateTime": "2031-03-12T15:00:00-04:00",
                "timeZone": "America/New_York",
            },
            end={
                "dateTime": "2031-03-12T16:00:00-04:00",
                "timeZone": "America/New_York",
            },
        )
        events = FakeEvents(
            by_id={
                "moved": moved,
                "cancelled": {"id": "cancelled", "status": "cancelled"},
                "deleted": 404,
                "purged": 410,
            }
        )
        gcal = MyDiaryGCal(service=FakeService(events))

        found = gcal.get_event("moved")
        assert found.start == pendulum.datetime(2031, 3, 12, 15, tz="America/New_York")
        assert gcal.get_event("cancelled") is None
        assert gcal.get_event("deleted") is None
        assert gcal.get_event("purged") is None

    def test_get_event_other_errors_raise(self):
        gcal = MyDiaryGCal(service=FakeService(FakeEvents(by_id={"x": 500})))

        with pytest.raises(HttpError):
            gcal.get_event("x")
