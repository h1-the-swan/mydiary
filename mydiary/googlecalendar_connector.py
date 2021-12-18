# -*- coding: utf-8 -*-

DESCRIPTION = """Get google calendar data using the Google Calendar API"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
from timeit import default_timer as timer
from typing import Dict, Optional

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

from .models import GoogleCalendarEvent

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


class MyDiaryGCal:
    def __init__(self, service: Optional[Resource] = None) -> None:
        self.service = service
        if self.service is None:
            gcal_token_file = os.environ["GOOGLECALENDAR_TOKEN_CACHE"]

            # If modifying these scopes, delete the token file
            SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
            creds = Credentials.from_authorized_user_file(gcal_token_file, SCOPES)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open("token.json", "w") as token:
                        token.write(creds.to_json())
                else:
                    raise RuntimeError(
                        "could not refresh the token. you'll need to authorize again."
                    )
            self.service = build("calendar", "v3", credentials=creds)

    # def get_articles_for_day(self, dt: datetime):
    #     dt = pendulum.instance(dt).set(hour=0, minute=0, second=0, microsecond=0)
    #     timestamp = dt.int_timestamp
    #     articles = []
    #     r = self.pocket_instance.get(state='all', since=timestamp)
    #     for item in r[0]['list'].values():
    #         a = PocketArticle.from_pocket_item(item)
    #         article_dt = pendulum.instance(a.time_updated)
    #         if article_dt.in_timezone(dt.timezone).date() == dt.date():
    #             articles.append(a)
    #     return articles
