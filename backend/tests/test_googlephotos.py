import os, json
from pathlib import Path

import pendulum


def test_env_loaded():
    assert "GOOGLEPHOTOS_TOKEN_CACHE" in os.environ

def test_googlephotos_api_call():
    from mydiary.googlephotos_connector import MyDiaryGooglePhotos
    dt = pendulum.parse("2022-03-24")
    mydiary_googlephotos = MyDiaryGooglePhotos()
    items = mydiary_googlephotos.query_photos_api_for_day(dt)
    assert len(items) > 0
    for item in items:
        thumbnail_url = mydiary_googlephotos.get_thumbnail_download_url(item)
        assert thumbnail_url.startswith("https")


# def test_gcal_api_call():
#     from mydiary.googlecalendar_connector import MyDiaryGCal
#     dt = pendulum.datetime(year=2018, month=8, day=30)
#     dt = pendulum.datetime(year=2018, month=8, day=30, tz='America/Los_Angeles')
#     events = MyDiaryGCal().get_events_for_day(dt)
#     event = events[0]
#     assert dt.is_same_day(event.start)
#     assert dt.is_same_day(event.end)

# def test_gcal_event(rootdir):
#     fp = Path(rootdir).joinpath("gcalevent.json")
#     article_json = json.loads(fp.read_text())
#     event = GoogleCalendarEvent.from_gcal_api_event(article_json)
#     assert event.summary == "Holiday in the Park!"
#     assert 'seattle' in event.location.lower()
#     assert pendulum.instance(event.start).in_tz('America/Los_Angeles') == event.start
#     assert pendulum.instance(event.end).in_tz('America/Los_Angeles') == event.end
