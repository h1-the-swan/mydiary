# -*- coding: utf-8 -*-

DESCRIPTION = """Get google calendar data using the Google Calendar API"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
from timeit import default_timer as timer
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Set

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.credentials import exceptions as GoogleOauthExceptions

from .db import engine, Session, select
from .models import GoogleCalendarEvent

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


@dataclass
class CalendarDay:
    """A day as Google lists it: the events that still stand, in start
    order, and the ids of the ones cancelled. Google only promises `id` and
    `status` on a cancelled event, so those are kept as bare ids."""

    events: List[GoogleCalendarEvent] = field(default_factory=list)
    cancelled_ids: Set[str] = field(default_factory=set)


class CalendarSource(Protocol):
    """What the app reads from Google Calendar (`MyDiaryGCal`)."""

    def get_day(self, dt: datetime) -> CalendarDay: ...

    def get_event(self, event_id: str) -> Optional[GoogleCalendarEvent]:
        """The event as it is now; None if it was cancelled or deleted."""
        ...


def _is_all_day(event: GoogleCalendarEvent) -> bool:
    # all-day events are stored as UTC midnight, shown in whatever zone the
    # process ran in (see `get_datetime_or_date`), and nothing else marks them
    start = event.start.in_timezone("UTC")
    end = event.end.in_timezone("UTC")
    return (
        end > start and start == start.start_of("day") and end == end.start_of("day")
    )


def _on_day(
    event: GoogleCalendarEvent, day_start: pendulum.DateTime, day_end: pendulum.DateTime
) -> bool:
    if _is_all_day(event):
        # by date, whatever zone the row was stored with; the end is exclusive
        start_date = event.start.in_timezone("UTC").date()
        end_date = event.end.in_timezone("UTC").date()
        return start_date <= day_start.date() < end_date
    # overlapping the day, the rule Google's timeMin / timeMax apply
    return event.start < day_end and event.end > day_start


def events_for_day(session: Session, dt: datetime) -> List[GoogleCalendarEvent]:
    """The day's Google Calendar events as the database has them, in start
    order, leaving out cancelled ones. The day is `dt`'s, in `dt`'s zone.
    Reads only the database."""
    day_start = pendulum.instance(dt).start_of("day")
    day_end = day_start.add(days=1)
    # the rows hold naive wall-clock times, each in its event's own zone, so
    # query a day wider on each side and filter exactly in Python
    lo = day_start.in_timezone("UTC").subtract(days=1).naive()
    hi = day_end.in_timezone("UTC").add(days=1).naive()
    rows = session.exec(
        select(GoogleCalendarEvent).where(
            GoogleCalendarEvent.start < hi,
            GoogleCalendarEvent.end > lo,
            GoogleCalendarEvent.status != "cancelled",
        )
    ).all()
    # an all-day event sorts at the day's start, as Google orders it; its
    # stored start is UTC midnight, the evening before in the Americas
    return sorted(
        (e for e in rows if _on_day(e, day_start, day_end)),
        key=lambda e: day_start if _is_all_day(e) else e.start,
    )


def _save_events(session: Session, events: List[GoogleCalendarEvent]) -> None:
    """Add `events` to the database, replacing the rows they already have."""
    logger.info(f"saving {len(events)} google calendar events to database")
    num_updated = 0
    for event in events:
        existing_row = session.get(GoogleCalendarEvent, event.id)
        if existing_row:
            session.delete(existing_row)
            num_updated += 1
        session.add(event)
    session.commit()
    for event in events:
        session.refresh(event)
    if num_updated > 0:
        logger.debug(
            f"{num_updated} events were already in the database and were updated"
        )


def save_calendar_day(
    session: Session, dt: datetime, day: CalendarDay, gcal: CalendarSource
) -> None:
    """Source Sync of the day's Google Calendar events: save `day` (as
    `gcal.get_day` listed it) to the database. A row the database had on the
    day that Google's listing left out is looked up by id: if it moved, its
    row takes the new times; if it was cancelled or deleted, its row is
    marked cancelled. Rows are never deleted. Nothing is written if a lookup
    fails."""
    listed = {e.id for e in day.events} | day.cancelled_ids
    moved = []
    gone = set(day.cancelled_ids)
    for row in events_for_day(session, dt):
        if row.id in listed:
            continue
        now = gcal.get_event(row.id)
        if now is None:
            gone.add(row.id)
        else:
            moved.append(now)
    _save_events(session, day.events + moved)
    for event_id in gone:
        row = session.get(GoogleCalendarEvent, event_id)
        if row is not None and row.status != "cancelled":
            row.status = "cancelled"
            session.add(row)
    session.commit()
    if moved or gone:
        logger.info(
            f"google calendar sync for {pendulum.instance(dt).to_date_string()}: "
            f"{len(moved)} moved, {len(gone)} cancelled"
        )


class MyDiaryGCal:
    def __init__(
        self, service: Optional[Resource] = None, init_service: bool = True
    ) -> None:
        self.service = service
        self.auth_error = None
        self.flow = None
        if init_service is True and self.service is None:
            self._init_service()

    def _init_service(self) -> None:
        gcal_token_file = os.environ["GOOGLECALENDAR_TOKEN_CACHE"]

        # If modifying these scopes, delete the token file
        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = Credentials.from_authorized_user_file(gcal_token_file, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except GoogleOauthExceptions.RefreshError as exc:
                    # TODO handle exception
                    # you'll need to authorize access again. see api.py get_gcal_auth_url() and refresh_gcal_token()
                    self.auth_error = exc
                    raise
                with open(gcal_token_file, "w") as token:
                    token.write(creds.to_json())
            else:
                raise RuntimeError(
                    "could not refresh the token. you'll need to authorize again."
                )
        self.service = build("calendar", "v3", credentials=creds)

    def _init_flow(self) -> None:
        gcal_credentials_file = os.environ["GOOGLECALENDAR_CREDENTIALS_FILE"]
        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        self.flow = InstalledAppFlow.from_client_secrets_file(
            gcal_credentials_file,
            SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
            # PKCE would require persisting the code_verifier between the
            # get_auth_url and refresh_token requests, which each build a new flow
            autogenerate_code_verifier=False,
        )

    def _save_token_cache(self) -> None:
        if not self.flow.credentials.valid:
            raise RuntimeError(
                "cannot save token cache, because credentials are not valid"
            )
        gcal_token_file = os.environ["GOOGLECALENDAR_TOKEN_CACHE"]
        with open(gcal_token_file, "w") as token:
            token.write(self.flow.credentials.to_json())

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    def get_day(self, dt: datetime) -> CalendarDay:
        """The day (`dt`'s, in `dt`'s zone) as Google lists it now, cancelled
        events included."""
        dt = pendulum.instance(dt).start_of("day")
        dt_max = dt.add(days=1)
        day = CalendarDay()
        page_token = None
        while True:
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=dt.to_rfc3339_string(),
                    timeMax=dt_max.to_rfc3339_string(),
                    singleEvents=True,
                    showDeleted=True,
                    orderBy="startTime",
                    pageToken=page_token,
                )
                .execute()
            )
            for item in events_result.get("items", []):
                if item.get("status") == "cancelled":
                    day.cancelled_ids.add(item["id"])
                else:
                    day.events.append(GoogleCalendarEvent.from_gcal_api_event(item))
            page_token = events_result.get("nextPageToken")
            if not page_token:
                return day

    def get_event(self, event_id: str) -> Optional[GoogleCalendarEvent]:
        """The event as Google has it now; None if it was cancelled, or is
        gone altogether."""
        try:
            item = (
                self.service.events()
                .get(calendarId="primary", eventId=event_id)
                .execute()
            )
        except HttpError as e:
            if e.resp.status in (404, 410):
                return None
            raise
        if item.get("status") == "cancelled":
            return None
        return GoogleCalendarEvent.from_gcal_api_event(item)

    def save_events_to_database(
        self, events: List[GoogleCalendarEvent], session: Optional[Session] = None
    ):
        if session is None:
            session = self.new_session()
        _save_events(session, events)
