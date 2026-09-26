# -*- coding: utf-8 -*-

import pendulum
import pytest
from sqlmodel import Session

from mydiary.mydiary_day import MyDiaryDay
from mydiary.song_practice import RunSummary

from tests.in_memory_joplin import InMemoryJoplin

DT = pendulum.datetime(2026, 9, 18, tz="America/New_York")
RUN = RunSummary("Paper Lanterns", "ukulele", ["Bridge"], DT.add(hours=20))


@pytest.fixture(autouse=True)
def no_pocket_db(monkeypatch):
    # init_markdown asks the real database for the Pocket cutoff; these days are
    # well after it either way
    monkeypatch.setattr(
        "mydiary.pocket_connector.get_pocket_section_cutoff",
        lambda session=None: pendulum.datetime(2025, 7, 8),
    )


def test_practice_section_after_spotify():
    md = MyDiaryDay(dt=DT, practice_runs=[RUN]).init_markdown()
    assert "## Practice\n\n- #song:paper-lanterns, ukulele: stumbled on Bridge" in md
    assert md.index("## Spotify tracks") < md.index("## Practice")


def test_no_section_without_runs():
    assert "## Practice" not in MyDiaryDay(dt=DT, practice_runs=[]).init_markdown()


BODY = (
    "# Sep 18, 2026\n\ntimezone: America/New_York\n\n## Words\n\n## Images\n\n"
    "## Google Calendar events\n\nNone\n\n## Spotify tracks\n\nNone\n"
)


def refresh(joplin: InMemoryJoplin, session: Session, runs) -> str:
    note_id = next(iter(joplin.notes))
    MyDiaryDay(dt=DT, practice_runs=runs, joplin_connector=joplin).update_joplin_note(
        session=session
    )
    return joplin.notes[note_id].body


def test_update_adds_section_to_an_existing_note(db_session: Session):
    joplin = InMemoryJoplin()
    joplin.add_note("2026-09-18", BODY)
    new_body = refresh(joplin, db_session, [RUN])
    assert "## Practice" in new_body
    assert "stumbled on Bridge" in new_body
    assert new_body.index("## Spotify tracks") < new_body.index("## Practice")


def test_update_without_runs_adds_no_section(db_session: Session):
    joplin = InMemoryJoplin()
    joplin.add_note("2026-09-18", BODY)
    assert "## Practice" not in refresh(joplin, db_session, [])


def test_update_replaces_the_section(db_session: Session):
    joplin = InMemoryJoplin()
    joplin.add_note("2026-09-18", BODY + "\n## Practice\n\n- an old run\n")
    new_body = refresh(joplin, db_session, [RUN])
    assert "an old run" not in new_body
    assert new_body.count("## Practice") == 1
    assert "stumbled on Bridge" in new_body
