import os, json
from pathlib import Path

import pendulum
from mydiary.models import GoogleCalendarEvent

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def test_env_loaded():
    assert "GOOGLECALENDAR_TOKEN_CACHE" in os.environ


def test_gcal_api_call():
    from mydiary.googlecalendar_connector import MyDiaryGCal
    dt = pendulum.datetime(year=2018, month=8, day=30)
    dt = pendulum.datetime(year=2018, month=8, day=30, tz='America/Los_Angeles')
    events = MyDiaryGCal().get_events_for_day(dt)
    event = events[0]
    assert dt.is_same_day(event.start)
    assert dt.is_same_day(event.end)

def test_gcal_event(rootdir):
    fp = Path(rootdir).joinpath("gcalevent.json")
    article_json = json.loads(fp.read_text())
    event = GoogleCalendarEvent.from_gcal_api_event(article_json)
    assert event.summary == "Holiday in the Park!"
    assert 'seattle' in event.location.lower()
    assert pendulum.instance(event.start).in_tz('America/Los_Angeles') == event.start
    assert pendulum.instance(event.end).in_tz('America/Los_Angeles') == event.end

    



