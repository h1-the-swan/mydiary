import pendulum
import pytest

from mydiary.mydiary_day import MyDiaryDay


def test_mydiary_day_from_dt():
    dt = pendulum.parse("2022-11-02")
    day = MyDiaryDay.from_dt(dt=dt, spotify_sync=False, gcal_save=False)
    assert dt.is_same_day(day.dt)
    assert len(day.google_calendar_events) > 0
    assert len(day.pocket_articles) > 0
    assert len(day.spotify_tracks) > 0
