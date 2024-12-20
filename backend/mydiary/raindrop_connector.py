# -*- coding: utf-8 -*-

DESCRIPTION = """Raindrop.io API (https://developer.raindrop.io/)"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
import requests
import backoff
from timeit import default_timer as timer
from typing import Dict, Generator, Iterable, List, Mapping, Optional, Tuple, Union

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from .db import engine, Session, select
from .models import PocketArticle, Tag

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


def get_ratelimit_wait_value(r: requests.Request) -> int:
    # The X-RateLimit-Reset value gives: The time at which the current rate limit window resets in UTC epoch seconds.
    ratelimit_reset = r.headers.get("x-ratelimit-reset")
    if ratelimit_reset:
        ratelimit_reset = int(ratelimit_reset)
        now = int(pendulum.now().timestamp())
        return ratelimit_reset - now + 2
    return 10  # default


class MyDiaryRaindrop:
    def __init__(self) -> None:
        self.base_url = "https://api.raindrop.io/rest/v1"
        self.access_token = os.getenv("RAINDROPIO_TEST_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        self.last_request: Optional[requests.Request] = None

    @property
    def ratelimit_remaining(self):
        if self.last_request is not None:
            ratelimit_reset = self.last_request.headers.get("x-ratelimit-reset")
            if ratelimit_reset:
                ratelimit_reset = int(ratelimit_reset)
                now = int(pendulum.now().timestamp())
                if ratelimit_reset >= now:
                    ratelimit_remaining = self.last_request.headers.get("x-ratelimit-remaining")
                    if ratelimit_remaining:
                        return int(ratelimit_remaining)
        return None

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    @backoff.on_predicate(
        backoff.runtime,
        predicate=lambda r: r.status_code == 429,
        value=get_ratelimit_wait_value,
        jitter=None,
    )
    def make_request(self, method="GET", url=None, headers=None, **kwargs) -> requests.Request:
        if url is None:
            # default url:
            url = f'{self.base_url}/raindrops/0'
        if headers is None:
            headers = self.headers
        self.last_request = requests.request(method=method, headers=headers, **kwargs)
        return self.last_request
