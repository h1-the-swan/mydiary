# -*- coding: utf-8 -*-

from types import SimpleNamespace

import pendulum
import pytest

from mydiary.mydiary_day import MyDiaryDay
from mydiary.song_practice import RunSummary

from tests.fakes import FakeJoplin, make_note

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


class RecordingJoplin(FakeJoplin):
    def __init__(self, notes):
        super().__init__(notes)
        self.bodies = {}

    def update_note_body(self, note_id, body):
        self.bodies[note_id] = body
        return SimpleNamespace(status_code=200)


def test_update_adds_section_to_an_existing_note(monkeypatch):
    monkeypatch.setattr(MyDiaryDay, "save_note_and_words_to_db", lambda self, session: None)
    body = (
        "# Sep 18, 2026\n\ntimezone: America/New_York\n\n## Words\n\n## Images\n\n"
        "## Google Calendar events\n\nNone\n\n## Spotify tracks\n\nNone\n"
    )
    note = make_note("2026-09-18", body, note_id="n1")
    joplin = RecordingJoplin([note])
    day = MyDiaryDay(dt=DT, practice_runs=[RUN], joplin_note_id="n1")
    day.update_joplin_note(session=None, joplin_connector=joplin)
    new_body = joplin.bodies["n1"]
    assert "## Practice" in new_body
    assert "stumbled on Bridge" in new_body
    assert new_body.index("## Spotify tracks") < new_body.index("## Practice")
