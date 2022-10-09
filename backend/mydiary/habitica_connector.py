# -*- coding: utf-8 -*-

DESCRIPTION = """Interact with the Habitica API"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
from timeit import default_timer as timer
from typing import Dict, Generator, Iterable, List, Optional, Tuple
import requests
from copy import deepcopy

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from .db import engine, Session, select

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


class MyDiaryHabitica:
    def __init__(self) -> None:
        self.user_id = os.environ["HABITICA_USER_ID"]
        self.access_token = os.environ["HABITICA_API_TOKEN"]
        self.app_name = "mydiary"

    # def new_session(self, engine=engine):
    #     with Session(engine) as session:
    #         return session

    def set_headers(self) -> Dict[str, str]:
        headers = {
            "x-client": f"{self.user_id}-{self.app_name}",
            "x-api-user": self.user_id,
            "x-api-key": self.access_token,
        }
        return headers

    def get_user_data(self) -> Dict:
        r = requests.get(
            "https://habitica.com/export/userdata.json", headers=self.set_headers()
        )
        r.raise_for_status()
        return r.json()

    def iseq_user_data(self, data1: Dict, data2: Dict) -> bool:
        # compares two habitica user data dicts and returns True if they are equal except for the updated field
        d1 = deepcopy(data1)
        d2 = deepcopy(data2)
        del d1["auth"]["timestamps"]["updated"]
        del d2["auth"]["timestamps"]["updated"]
        return d1 == d2
