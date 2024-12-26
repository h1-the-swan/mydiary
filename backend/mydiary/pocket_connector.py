# -*- coding: utf-8 -*-

DESCRIPTION = """Get pocket data using the Pocket API and the pocket library"""

import sys, os, time
from pathlib import Path
from datetime import date, datetime
import pendulum
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

from pocket import Pocket

from .db import engine, Session, select
from .models import PocketArticle, Tag

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())


class MyDiaryPocket:
    def __init__(self, pocket_instance: Optional[Pocket] = None) -> None:
        self.pocket_instance = pocket_instance
        if self.pocket_instance is None:
            consumer_key = os.environ["POCKET_CONSUMER_KEY"]
            access_token = os.environ["POCKET_ACCESS_TOKEN"]
            self.pocket_instance = Pocket(consumer_key, access_token)

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    def get_articles_for_day(
        self, dt: datetime, session: Optional[Session] = None
    ) -> Dict[str, List[PocketArticle]]:
        if session is None:
            session = self.new_session()
        dt = pendulum.instance(dt)
        start = dt.start_of("day").in_timezone("UTC")
        end = dt.end_of("day").in_timezone("UTC")
        articles = {}
        for k in ["added", "read", "favorited"]:
            attr = getattr(PocketArticle, f"time_{k}")
            stmt = (
                select(PocketArticle)
                .where(PocketArticle.status != 2)
                .where(attr >= start)
                .where(attr <= end)
                .order_by(attr)
            )
            r = session.exec(stmt).all()
            articles[k] = r
        return articles

    def yield_all_articles_from_api_json(
        self,
        state: str = "all",
        detailType: str = "complete",
        since: Optional[int] = None,
        offset: int = 0,
        count: int = 30,
    ) -> Iterable[PocketArticle]:
        while True:
            r = self.pocket_instance.get(
                state=state,
                detailType=detailType,
                since=since,
                offset=offset,
                count=count,
            )
            if r[0]["status"] != 1:
                break
            this_total = r[0].get("total")
            if this_total:
                this_total = int(this_total)
                if count + offset > this_total:
                    break
            items_dict: Dict = r[0]["list"]
            if len(items_dict) == 0:
                break
            for item in items_dict.values():
                yield item

            offset += count

    def yield_all_articles_from_api(
        self,
        state: str = "all",
        detailType: str = "complete",
        since: Optional[int] = None,
        offset: int = 0,
        count: int = 30,
    ) -> Iterable[PocketArticle]:
        for item in self.yield_all_articles_from_api_json(
            state=state, detailType=detailType, since=since, offset=offset, count=count
        ):
            yield PocketArticle.from_pocket_item(item)

    def get_all_articles_from_api(
        self,
        state: str = "all",
        detailType: str = "complete",
        since: Optional[int] = None,
        count: int = 5000,
    ) -> List[PocketArticle]:
        return list(
            self.yield_all_articles_from_api(
                state=state, detailType=detailType, since=since, count=count
            )
        )

    def collect_tags(
        self,
        article: PocketArticle,
        pocket_tags: List[str],
        session: Optional[Session] = None,
        commit=True,
    ) -> PocketArticle:
        """Add tags to database if they are not already there

        Args:
            article (PocketArticle): PocketArticle instance
            pocket_tags (List[str]): list of tags
            session (Optional[Session], optional): database session. Defaults to None.

        Returns:
            PocketArticle: the PocketArticle instance (unchanged)
        """
        if session is None:
            session = self.new_session()
        for tag_name in pocket_tags:
            tag = session.exec(select(Tag).where(Tag.name == tag_name)).one_or_none()
            if tag is None:
                tag = Tag(name=tag_name)
            tag.is_pocket_tag = True
            session.add(tag)
            article.tags.append(tag)
        if commit is True:
            session.commit()
        return article

    def save_articles_to_database(
        self,
        articles: Union[Iterable[PocketArticle], Dict[str, List[PocketArticle]]],
        session: Optional[Session] = None,
    ):
        if isinstance(articles, Mapping):
            articles_list = []
            added_ids = set()
            for v in articles.values():
                for article in v:
                    if article.id not in added_ids:
                        articles_list.append(article)
                        added_ids.add(article.id)
        else:
            articles_list = articles
        logger.info(f"saving {len(articles_list)} pocket articles to database")
        if session is None:
            session = self.new_session()
        num_updated = 0
        for article in articles_list:
            existing_row = session.get(PocketArticle, article.id)
            if existing_row:
                # TODO: merge instead of delete
                session.delete(existing_row)
                session.commit()
                num_updated += 1
            session.merge(article)
            # article.collect_tags(session=session, commit=False)
        session.commit()
        # for article in articles_list:
        #     session.refresh(article)
        if num_updated > 0:
            logger.debug(
                f"{num_updated} articles were already in the database and were updated"
            )
