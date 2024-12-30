import pendulum
import pytest

from mydiary.mydiary_day import MyDiaryDay
from sqlmodel import Session, SQLModel, create_engine, select


def test_mydiary_day_from_dt():
    dt = pendulum.parse("2022-11-02")
    day = MyDiaryDay.from_dt(dt=dt, spotify_sync=False, gcal_save=False)
    assert dt.is_same_day(day.dt)
    assert len(day.google_calendar_events) > 0
    assert len(day.pocket_articles) > 0
    assert len(day.spotify_tracks) > 0


def test_mydiary_day_from_loaded_db(loaded_db: Session):
    dt = pendulum.datetime(2024, 10, 19, tz="America/New_York")
    day = MyDiaryDay.from_dt(
        dt=dt, session=loaded_db, spotify_sync=False, gcal_save=False
    )
    md = day.init_markdown()
    assert md.startswith("# Oct 19, 2024")
