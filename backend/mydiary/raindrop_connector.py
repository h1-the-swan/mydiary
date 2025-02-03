# -*- coding: utf-8 -*-

DESCRIPTION = """Raindrop.io API (https://developer.raindrop.io/)"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import json
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
from sqlalchemy import desc

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())

# ID for the raindrop.io Collection which has items from Pocket
RAINDROP_POCKET_COLLECTION_ID = 50346946


def get_ratelimit_wait_value(r: requests.Request) -> int:
    # The X-RateLimit-Reset value gives: The time at which the current rate limit window resets in UTC epoch seconds.
    ratelimit_reset = r.headers.get("x-ratelimit-reset")
    if ratelimit_reset:
        ratelimit_reset = int(ratelimit_reset)
        now = int(pendulum.now().timestamp())
        return ratelimit_reset - now + 2
    return 10  # default


class MyDiaryRaindrop:
    def __init__(
        self, raindrop_pocket_collection_id: int = RAINDROP_POCKET_COLLECTION_ID
    ) -> None:
        self.base_url = "https://api.raindrop.io/rest/v1"
        self.access_token = os.getenv("RAINDROPIO_TEST_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        self.last_response: Optional[requests.Response] = None
        self.raindrop_pocket_collection_id = raindrop_pocket_collection_id

    @property
    def ratelimit_remaining(self):
        if self.last_response is not None:
            ratelimit_reset = self.last_response.headers.get("x-ratelimit-reset")
            if ratelimit_reset:
                ratelimit_reset = int(ratelimit_reset)
                now = int(pendulum.now().timestamp())
                if ratelimit_reset >= now:
                    ratelimit_remaining = self.last_response.headers.get(
                        "x-ratelimit-remaining"
                    )
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
    def make_request(
        self, method="GET", url=None, headers=None, **kwargs
    ) -> requests.Response:
        if url is None:
            # default url:
            url = f"{self.base_url}/raindrops/0"
        if headers is None:
            headers = self.headers
        self.last_response = requests.request(
            method=method, url=url, headers=headers, **kwargs
        )
        return self.last_response

    def get_raindrop_by_id(self, raindrop_id: int) -> dict:
        url = f"{self.base_url}/raindrop/{raindrop_id}"
        r = self.make_request(method="GET", url=url)
        if r.status_code == 404:
            logger.debug(f"raindrop with ID {raindrop_id} does not exist")
            return None
        r.raise_for_status()
        return r.json()["item"]

    def raindrop_dict_from_mydiary_pocket_article(
        self,
        article: PocketArticle,
        include_link: bool = True,
        request_parse: bool = True,
        note: str | None = None,
    ) -> dict:
        drop = {
            "important": article.favorite,
            "tags": article.tags_str,
            "collection": {"$id": self.raindrop_pocket_collection_id},
        }
        if include_link is True:
            drop["link"] = article.url
        if request_parse is True:
            drop["pleaseParse"] = {}
        if article.archived is True:
            drop["tags"].append("archived")
        if note is not None:
            drop["note"] = note
        return drop

    def _ensure_list(self, items: Iterable[dict] | dict) -> list[dict]:
        if isinstance(items, dict):
            items = [items]
        else:
            items = list(items)
        return items

    def create_drops(self, drops: Iterable[dict] | dict) -> requests.Response:
        drops = self._ensure_list(drops)
        payload = {"items": drops}
        return self.make_request(
            method="POST", url=f"{self.base_url}/raindrops", json=payload
        )

    def update_drop(self, drop_id: int, body: dict) -> requests.Response:
        url = f"{self.base_url}/raindrop/{drop_id}"
        return self.make_request(method="PUT", url=url, json=body)

    def delete_drop(self, drop_id: int) -> requests.Response:
        return self.make_request(
            method="DELETE", url=f"{self.base_url}/raindrop/{drop_id}"
        )

    def note_content_from_article_db(self, article: PocketArticle) -> dict:
        return {
            "pocket_id": article.id,
            "status": article.status.value,
            "time_added": int(article.time_added.timestamp()),
            "time_updated": int(article.time_updated.timestamp()),
        }

    def create_drops_from_articles(
        self,
        articles: list[PocketArticle],
        session: Session,
        post_commit: bool = True,
        update_time: datetime | None = None,
    ) -> list[PocketArticle]:
        # bulk create
        api_create_limit_per_request = 100
        drops_to_create: list[dict] = []
        added = []
        if update_time is None:
            update_time = pendulum.now().in_timezone("UTC")
        for article_db in articles:
            drop = self.raindrop_dict_from_mydiary_pocket_article(
                article_db,
                note=json.dumps(self.note_content_from_article_db(article_db)),
            )
            drops_to_create.append(drop)

        for i in range(0, len(drops_to_create), api_create_limit_per_request):
            this_drops = drops_to_create[i : i + api_create_limit_per_request]
            r = self.create_drops(this_drops)
            for item in r.json()["items"]:
                fields_to_check_for_id = ["_id", "$id", "id"]
                for f in fields_to_check_for_id:
                    raindrop_id = item.get(f, None)
                    if raindrop_id is not None:
                        break
                if raindrop_id is None:
                    raise RuntimeError(f"Failed to get raindrop_id from item {item}")
                raindrop_note = json.loads(item["note"])
                article_id = raindrop_note["pocket_id"]
                article_db = session.get(PocketArticle, article_id)
                article_db.raindrop_id = raindrop_id
                article_db.time_pocket_raindrop_sync = update_time
                session.add(article_db)
                added.append(article_db)
        if post_commit is True:
            session.commit()
        return added

    def update_drops_from_articles(
        self,
        articles: list[PocketArticle],
        session: Session,
        post_commit: bool = True,
        update_time: datetime | None = None,
    ) -> list[PocketArticle]:
        # API currently only allows bulk update if parameters are all the same (i.e., updating all of them with the same new tags, etc.)
        # so we have to make one request per item to update
        updated = []
        if update_time is None:
            update_time = pendulum.now().in_timezone("UTC")
        for article_db in articles:
            drop = self.raindrop_dict_from_mydiary_pocket_article(
                article_db,
                include_link=False,
                request_parse=False,
                note=json.dumps(self.note_content_from_article_db(article_db)),
            )
            r = self.update_drop(article_db.raindrop_id, drop)
            r.raise_for_status()
            article_db.time_pocket_raindrop_sync = update_time
            session.add(article_db)
            updated.append(article_db)
        if post_commit is True:
            session.commit()
        return updated

    def create_or_update_drops_from_articles(
        self,
        articles: list[PocketArticle],
        session: Session,
        post_commit: bool = True,
        update_time: datetime | None = None,
    ) -> dict[str, list[PocketArticle]]:
        if update_time is None:
            update_time = pendulum.now().in_timezone("UTC")
        # separate into existing (need to updated) and new (need to create)
        to_create: list[PocketArticle] = []
        to_update: list[PocketArticle] = []
        for article_db in articles:
            if not article_db.raindrop_id:
                to_create.append(article_db)
            else:
                to_update.append(article_db)
        added = self.create_drops_from_articles(
            to_create, session=session, post_commit=False, update_time=update_time
        )
        updated = self.update_drops_from_articles(
            to_update, session=session, post_commit=False, update_time=update_time
        )
        if post_commit is True:
            session.commit()
        return {"added": added, "updated": updated}

    def sync_recent_pocket_to_raindrop(
        self, session: Session, since: datetime | None = None, post_commit: bool = True
    ) -> dict[str, int]:
        if since is None:
            # get time of last sync
            stmt = (
                select(PocketArticle)
                .filter(PocketArticle.time_pocket_raindrop_sync != None)
                .order_by(desc(PocketArticle.time_pocket_raindrop_sync))
            )
            r = session.exec(stmt).first()
            since = r.time_pocket_raindrop_sync
        now = pendulum.now().in_timezone("UTC")
        articles_db: list[PocketArticle] = session.exec(
            select(PocketArticle)
            .filter(PocketArticle.time_updated >= since)
            .filter(PocketArticle.time_last_api_sync > since)
        ).all()

        try:
            result = self.create_or_update_drops_from_articles(
                articles_db, session=session, post_commit=False, update_time=now
            )
        finally:
            if post_commit is True:
                session.commit()

        logger.debug(
            f"""{len(result["added"])} pocket articles added to raindrop.io. {len(result["updated"])} raindrop.io articles updated from local db."""
        )
        return {
            "added": len(result["added"]),
            "updated": len(result["updated"]),
        }
