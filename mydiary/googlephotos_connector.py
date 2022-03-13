# -*- coding: utf-8 -*-

DESCRIPTION = """connector for the Google Photos API"""

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


class MyDiaryGooglePhotos:
    def __init__(self, service: Optional[Resource] = None) -> None:
        self.service = service
        self.auth_error = None
        if self.service is None:
            token_file = os.environ["GOOGLEPHOTOS_TOKEN_CACHE"]

            # If modifying these scopes, delete the token file
            SCOPES = ["https://www.googleapis.com/auth/photoslibrary.readonly"]
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except GoogleOauthExceptions.RefreshError as exc:
                        # TODO handle exception
                        # you'll need to authorize access again. the procedure is currently in googlephotos-auth-example.ipynb
                        self.auth_error = exc
                        raise
                    with open(token_file, "w") as token:
                        token.write(creds.to_json())
                else:
                    raise RuntimeError(
                        "could not refresh the token. you'll need to authorize again."
                    )
            # photos API is currently not explicitly supported by the python client, so need to use static_discovery=False
            self.service = build(
                "photoslibrary", "v1", credentials=creds, static_discovery=False
            )

    # def new_session(self, engine=engine):
    #     with Session(engine) as session:
    #         return session

    def get_api_date_obj(self, dt: pendulum.DateTime):
        return {
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
        }

    def query_photos_api_for_day(self, dt: datetime):
        # dt = pendulum.instance(dt).set(hour=0, minute=0, second=0, microsecond=0)
        dt = pendulum.instance(dt).start_of("day")
        filters = {"dateFilter": {"dates": [self.get_api_date_obj(dt)]}}
        r = self.service.mediaItems().search(body={"filters": filters}).execute()
        mediaItems = r.get("mediaItems", [])
        return mediaItems

    def get_thumbnail_download_url(self, item, w=512, h=512) -> str:
        return f"{item['baseUrl']}=w{w}-h{h}"
