# -*- coding: utf-8 -*-

DESCRIPTION = """Access Pocket articles stored in the mydiary database.

Pocket was shut down on 2025-07-08 and its API no longer exists, so the
integration is deprecated: no new data is fetched, but articles already
saved to the database are kept and remain readable/editable. Diary entries
for days after the latest Pocket item in the database no longer include a
Pocket articles section (see get_pocket_section_cutoff)."""

from datetime import datetime
import pendulum
from typing import Dict, Iterable, List, Mapping, Optional, Union

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from sqlalchemy import func

from .db import engine, Session, select
from .models import PocketArticle, PocketArticleUpdate, Tag

POCKET_SHUTDOWN_DATE = pendulum.datetime(2025, 7, 8, tz="UTC")


def get_pocket_section_cutoff(session: Optional[Session] = None) -> pendulum.DateTime:
    """Datetime of the latest Pocket item in the database.

    Diary entries for days after this datetime do not include a Pocket
    articles section. Falls back to POCKET_SHUTDOWN_DATE if the database
    contains no Pocket articles.
    """
    if session is None:
        session = Session(engine)
    times = []
    for col in (
        PocketArticle.time_added,
        PocketArticle.time_updated,
        PocketArticle.time_read,
        PocketArticle.time_favorited,
    ):
        t = session.exec(select(func.max(col))).one()
        if t is not None:
            times.append(pendulum.instance(t))
    return max(times) if times else POCKET_SHUTDOWN_DATE


class MyDiaryPocket:
    """Database-only access to Pocket articles (the Pocket API is defunct)."""

    def new_session(self, engine=engine):
        with Session(engine) as session:
            return session

    def get_articles_for_day(
        self, dt: datetime, session: Optional[Session] = None
    ) -> Dict[str, List[PocketArticle]]:
        dt = pendulum.instance(dt)
        if session is None:
            session = self.new_session()
        if dt.start_of("day") > get_pocket_section_cutoff(session=session):
            return {"added": [], "read": [], "favorited": []}
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

    def update_article(
        self,
        db_article: PocketArticle,
        article_update: PocketArticleUpdate,
        session: Optional[Session] = None,
        post_commit: bool = True,
    ) -> PocketArticle:
        if session is None:
            session = self.new_session()
        article_data = article_update.model_dump(exclude_unset=True)
        db_article.sqlmodel_update(article_data)
        if article_data.get("pocket_tags"):
            new_tags = []
            # sqlalchemy is weird. I couldn't get the merge to work right, so instead I avoid creating new Tag objects if they already exist
            existing_tags = session.exec(select(Tag)).all()
            existing_tags_map = {t.name: t for t in existing_tags}
            for tag_name in article_data["pocket_tags"]:
                if tag_name in existing_tags_map:
                    new_tags.append(existing_tags_map[tag_name])
                else:
                    new_tags.append(Tag(name=tag_name, is_pocket_tag=True))
            db_article.tags = new_tags
        session.merge(db_article)
        if post_commit is True:
            session.commit()
        return db_article
