# -*- coding: utf-8 -*-

DESCRIPTION = """Get google calendar data using the Google Calendar API"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
from timeit import default_timer as timer
from typing import Dict, List, Optional

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from googleapiclient.discovery import build, Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.credentials import exceptions as GoogleOauthExceptions

from .db import engine, Session, select
from .models import GoogleCalendarEvent

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


class MyDiaryGCal:
    def __init__(self, service: Optional[Resource] = None) -> None:
        self.service = service
        self.auth_error = None
        if self.service is None:
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
                        # you'll need to authorize access again. the procedure is currently in googlecalendar-auth-example.ipynb
                        self.auth_error = exc
                        raise
                    with open(gcal_token_file, "w") as token:
                        token.write(creds.to_json())
                else:
                    raise RuntimeError(
                        "could not refresh the token. you'll need to authorize again."
                    )
            self.service = build("calendar", "v3", credentials=creds)

    def get_events_for_day(self, dt: datetime) -> List[GoogleCalendarEvent]:
        # dt = pendulum.instance(dt).set(hour=0, minute=0, second=0, microsecond=0)
        dt = pendulum.instance(dt).start_of("day")
        dt_max = dt.add(days=1)
        calendarId = "primary"
        # TODO this only gets events that start and end on the given date. should probably get all events that start on or before date and end on or after date
        events_result = (
            self.service.events()
            .list(
                calendarId=calendarId,
                timeMin=dt.to_rfc3339_string(),
                timeMax=dt_max.to_rfc3339_string(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        return [GoogleCalendarEvent.from_gcal_api_event(e) for e in events]

    def save_events_to_database(self, events: List[GoogleCalendarEvent]):
        logger.info(f"saving {len(events)} google calendar events to database")
        with Session(engine) as session:
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
            logger.debug(f"{num_updated} events were already in the database and were updated")
