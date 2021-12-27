# -*- coding: utf-8 -*-

DESCRIPTION = """Get pocket data using the Pocket API and the pocket library"""

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

from pocket import Pocket

from .models import PocketArticle

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


class MyDiaryPocket:
    def __init__(self, pocket_instance: Optional[Pocket] = None) -> None:
        self.pocket_instance = pocket_instance
        if self.pocket_instance is None:
            consumer_key = os.environ["POCKET_CONSUMER_KEY"]
            access_token = os.environ["POCKET_ACCESS_TOKEN"]
            self.pocket_instance = Pocket(consumer_key, access_token)

    def get_articles_for_day(self, dt: datetime) -> Dict[str, List[PocketArticle]]:
        dt = pendulum.instance(dt).set(hour=0, minute=0, second=0, microsecond=0)
        timestamp = dt.int_timestamp
        articles = {
            'added': [],
            # 'updated': [],
            'read': [],
            'favorited': [],
        }
        r = self.pocket_instance.get(state="all", since=timestamp)
        items_dict = r[0]["list"]
        if items_dict:
            for item in r[0]["list"].values():
                a = PocketArticle.from_pocket_item(item)
                if a.status == "SHOULD_BE_DELETED":
                    continue
                for k in articles.keys():
                    article_dt = getattr(a, f"time_{k}", None)
                    if article_dt:
                        article_dt = pendulum.instance(article_dt)
                        if article_dt.in_timezone(dt.timezone).date() == dt.date():
                            articles[k].append(a)
        return articles
