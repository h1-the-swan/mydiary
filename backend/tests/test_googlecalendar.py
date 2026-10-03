import os, json
from pathlib import Path

import pendulum
import pytest
from mydiary.models import GoogleCalendarEvent
from sqlmodel import Session, SQLModel, create_engine, select

from mydiary.googlecalendar_connector import MyDiaryGCal

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


def test_env_loaded():
    assert "GOOGLECALENDAR_TOKEN_CACHE" in os.environ


@pytest.mark.external_api
def test_gcal_api_call():
    dt = pendulum.datetime(year=2018, month=8, day=30, tz="America/Los_Angeles")
    events = MyDiaryGCal().get_events_for_day(dt)
    event = events[0]
    assert dt.is_same_day(event.start)
    assert dt.is_same_day(event.end)


def test_gcal_event(rootdir, db_session: Session):
    fp = Path(rootdir).joinpath("gcalevent.json")
    article_json = json.loads(fp.read_text())
    event = GoogleCalendarEvent.from_gcal_api_event(article_json)
    assert event.summary == "Holiday in the Park!"
    assert "seattle" in event.location.lower()
    assert pendulum.instance(event.start).in_tz("America/Los_Angeles") == event.start
    assert pendulum.instance(event.end).in_tz("America/Los_Angeles") == event.end

    mydiary_gcal = MyDiaryGCal()
    mydiary_gcal.save_events_to_database([event], db_session)
    
    db_events = db_session.exec(select(GoogleCalendarEvent)).all()
    db_event = db_events[0]
    assert len(db_events) == 1
    assert db_event.summary == "Holiday in the Park!"
    assert "seattle" in db_event.location.lower()
    assert pendulum.instance(db_event.start).in_tz("America/Los_Angeles") == event.start
    assert pendulum.instance(db_event.end).in_tz("America/Los_Angeles") == event.end

    # update
    new_end = pendulum.parse("2021-12-09T21:00:00-08:00").in_timezone(tz="America/Los_Angeles")
    db_event.end = new_end
    mydiary_gcal.save_events_to_database([event], db_session)
    db_events = db_session.exec(select(GoogleCalendarEvent)).all()
    db_event = db_events[0]
    assert len(db_events) == 1
    assert db_event.summary == "Holiday in the Park!"
    assert "seattle" in db_event.location.lower()
    assert pendulum.instance(db_event.start).in_tz("America/Los_Angeles") == event.start
    assert pendulum.instance(db_event.end).in_tz("America/Los_Angeles") == new_end


def _api_event(**fields):
    # made up, shaped like an events.list item
    event = {
        "id": "made-up-event-1",
        "summary": "Made-up event",
        "start": {"dateTime": "2031-03-10T09:00:00-04:00", "timeZone": "America/New_York"},
        "end": {"dateTime": "2031-03-10T10:00:00-04:00", "timeZone": "America/New_York"},
    }
    event.update(fields)
    return event


def test_gcal_event_status_defaults_to_confirmed():
    assert GoogleCalendarEvent.from_gcal_api_event(_api_event()).status == "confirmed"


def test_untitled_event_gets_an_empty_summary(db_session: Session):
    api_event = _api_event()
    del api_event["summary"]
    db_session.add(GoogleCalendarEvent.from_gcal_api_event(api_event))
    db_session.commit()
    assert db_session.get(GoogleCalendarEvent, "made-up-event-1").summary == ""


def test_cancelled_recurring_instance_keeps_its_status(db_session: Session):
    # what events.list(showDeleted=True, singleEvents=True) returns for a
    # cancelled instance of a recurring event: full start and end
    api_event = _api_event(
        id="made-up-series_20310310T130000Z",
        status="cancelled",
        recurringEventId="made-up-series",
        originalStartTime={
            "dateTime": "2031-03-10T09:00:00-04:00",
            "timeZone": "America/New_York",
        },
    )
    db_session.add(GoogleCalendarEvent.from_gcal_api_event(api_event))
    db_session.commit()
    db_session.expire_all()
    row = db_session.get(GoogleCalendarEvent, "made-up-series_20310310T130000Z")
    assert row.status == "cancelled"
