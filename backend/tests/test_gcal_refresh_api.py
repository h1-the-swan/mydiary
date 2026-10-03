# -*- coding: utf-8 -*-
"""The Google Calendar Refresh routes: preview, apply, and how each failure
reaches the dialog."""

from collections import Counter

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from mydiary import googlecalendar_connector
from mydiary.api import app, get_gcal, get_joplin_port, get_session
from mydiary.diary_note import section_content
from mydiary.models import GoogleCalendarEvent
from mydiary.mydiary_day import google_calendar_events_markdown
from tests.in_memory_joplin import InMemoryJoplin
from tests.test_gcal_refresh import (
    TITLE,
    FakeCalendar,
    event,
    made_up_events,
    note_body,
)

PREVIEW = f"/joplin/gcal_refresh_preview/{TITLE}"
APPLY = f"/joplin/gcal_refresh/{TITLE}"
# the diary's timezone is inferred from TimeZoneChange rows, which these
# tests don't have; pin it
PARAMS = {"tz": "America/New_York"}


class RecordingCalendar(FakeCalendar):
    """A FakeCalendar that remembers the day it was asked for, and can fail."""

    def __init__(self, *args, error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.days = []
        self.error = error

    def get_events_for_day(self, dt):
        self.days.append(dt)
        if self.error:
            raise self.error
        return super().get_events_for_day(dt)


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def joplin() -> InMemoryJoplin:
    return InMemoryJoplin()


@pytest.fixture
def gcal() -> RecordingCalendar:
    return RecordingCalendar(made_up_events())


@pytest.fixture
def client(session, joplin, gcal):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_joplin_port] = lambda: joplin
    app.dependency_overrides[get_gcal] = lambda: gcal
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def stale_note(joplin) -> str:
    return joplin.add_note(
        TITLE, note_body(google_calendar_events_markdown(made_up_events()[:1]))
    )


def test_operation_ids_are_unique():
    ids = Counter(r.operation_id for r in app.routes if isinstance(r, APIRoute))
    assert [i for i, n in ids.items() if i and n > 1] == []


class TestPreviewRoute:
    def test_returns_the_diff(self, client, joplin, stale_note, session):
        r = client.get(PREVIEW, params=PARAMS)

        assert r.status_code == 200
        data = r.json()
        assert data["changed"] is True
        assert data["after"] == google_calendar_events_markdown(made_up_events())
        assert {"op": "add", "text": made_up_events()[1].to_markdown()} in data["diff"]
        assert joplin.updates == []
        assert session.exec(select(GoogleCalendarEvent)).all() == []

    def test_uses_the_requested_day_and_timezone(self, client, gcal, stale_note):
        client.get(PREVIEW, params={"tz": "UTC"})

        (day,) = gcal.days
        assert day.timezone_name == "UTC"
        assert day.to_date_string() == TITLE

    def test_no_note(self, client):
        r = client.get(PREVIEW, params=PARAMS)
        assert r.status_code == 404

    def test_google_failing(self, client, gcal, stale_note):
        gcal.error = RuntimeError("token expired")

        r = client.get(PREVIEW, params=PARAMS)

        assert r.status_code == 502
        assert "token expired" in r.json()["detail"]

    def test_unreadable_section(self, client, joplin):
        joplin.add_note(TITLE, note_body("None") + "## Google Calendar events\n\nx\n")

        r = client.get(PREVIEW, params=PARAMS)

        assert r.status_code == 422


class TestApplyRoute:
    def test_writes_the_section(self, client, joplin, stale_note, gcal, session):
        preview = client.get(PREVIEW, params=PARAMS).json()

        r = client.post(
            APPLY,
            params=PARAMS,
            json={"before": preview["before"], "after": preview["after"]},
        )

        assert r.status_code == 200
        assert r.json() == {"wrote": True}
        body = joplin.notes[stale_note].body
        assert section_content(body, "Google Calendar events") == preview["after"]
        assert len(gcal.saved) == 1

    def test_calendar_changed(self, client, joplin, stale_note, gcal):
        preview = client.get(PREVIEW, params=PARAMS).json()
        gcal.events = gcal.events + [event("ev3", "Call the plumber", 17)]

        r = client.post(
            APPLY,
            params=PARAMS,
            json={"before": preview["before"], "after": preview["after"]},
        )

        assert r.status_code == 409
        assert "calendar" in r.json()["detail"]
        assert joplin.updates == []

    def test_note_changed(self, client, joplin, stale_note):
        preview = client.get(PREVIEW, params=PARAMS).json()
        joplin.edit_note(stale_note, note_body("None"))

        r = client.post(
            APPLY,
            params=PARAMS,
            json={"before": preview["before"], "after": preview["after"]},
        )

        assert r.status_code == 409
        assert "note" in r.json()["detail"]
        assert joplin.updates == []

    def test_no_note(self, client):
        r = client.post(APPLY, params=PARAMS, json={"before": "", "after": "None"})
        assert r.status_code == 404


def test_google_not_set_up(session, joplin, monkeypatch):
    """Without the override, a calendar that can't be built is a 502 with
    the reason, not a 500."""

    def broken(*args, **kwargs):
        raise RuntimeError("could not refresh the token")

    monkeypatch.setattr(googlecalendar_connector, "MyDiaryGCal", broken)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_joplin_port] = lambda: joplin
    try:
        r = TestClient(app).get(PREVIEW, params=PARAMS)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 502
    assert "could not refresh the token" in r.json()["detail"]


class TestApplyRouteFailures:
    def test_unchanged_reports_no_write(self, client, joplin):
        md = google_calendar_events_markdown(made_up_events())
        joplin.add_note(TITLE, note_body(md))

        r = client.post(APPLY, params=PARAMS, json={"before": md, "after": md})

        assert r.status_code == 200
        assert r.json() == {"wrote": False}

    def test_unreadable_section(self, client, joplin):
        body = note_body("None") + "## Google Calendar events\n\nx\n"
        note_id = joplin.add_note(TITLE, body)

        r = client.post(
            APPLY,
            params=PARAMS,
            json={
                "before": "",
                "after": google_calendar_events_markdown(made_up_events()),
            },
        )

        assert r.status_code == 422
        assert joplin.notes[note_id].body == body

    def test_google_failing(self, client, gcal, stale_note, joplin):
        gcal.error = RuntimeError("token expired")

        r = client.post(APPLY, params=PARAMS, json={"before": "", "after": "None"})

        assert r.status_code == 502
        assert "token expired" in r.json()["detail"]
        assert joplin.updates == []
