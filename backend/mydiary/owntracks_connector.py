# -*- coding: utf-8 -*-

DESCRIPTION = """Get location history from an OwnTracks recorder instance.

The recorder's HTTP API is tiny: /api/0/list enumerates users and their devices,
and /api/0/locations returns the fixes for one device over a time range. Both
`user` and `device` are required for a locations query, so devices have to be
enumerated first and their results unioned -- replacing a phone (or reinstalling
the app) creates a new device id, and history is split across them."""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pendulum
import requests

from .db import Session, engine, select
from .models import OwnTracksLocation

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


OWNTRACKS_RECORDER_URL = (
    os.environ.get("OWNTRACKS_RECORDER_URL") or "http://localhost:8083"
)
OWNTRACKS_USER = os.environ.get("OWNTRACKS_USER") or ""

# the recorder returns everything for the range in one response; these days are
# tens of points, so there is no pagination to worry about
REQUEST_TIMEOUT = 30


class MyDiaryOwnTracks:
    def __init__(
        self,
        url: str = OWNTRACKS_RECORDER_URL,
        user: str = OWNTRACKS_USER,
    ) -> None:
        self.url = url.rstrip("/")
        self.user = user

    def new_session(self, engine=engine) -> Session:
        return Session(engine)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        r = requests.get(
            f"{self.url}{path}", params=params or {}, timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return r.json()

    def list_users(self) -> List[str]:
        return self._get("/api/0/list").get("results", [])

    def list_devices(self, user: Optional[str] = None) -> List[str]:
        user = user or self.user
        if not user:
            raise RuntimeError("no OwnTracks user configured (set OWNTRACKS_USER)")
        return self._get("/api/0/list", {"user": user}).get("results", [])

    def fetch_locations(
        self,
        start: datetime,
        end: datetime,
        device: str,
        user: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch raw location dicts for one device over [start, end)."""
        user = user or self.user
        start = pendulum.instance(start).in_timezone("UTC")
        end = pendulum.instance(end).in_timezone("UTC")
        data = self._get(
            "/api/0/locations",
            {
                "user": user,
                "device": device,
                "from": start.format("YYYY-MM-DDTHH:mm:ss"),
                "to": end.format("YYYY-MM-DDTHH:mm:ss"),
                "format": "json",
            },
        )
        items = data.get("data", [])
        # the recorder omits these from the payload when querying by device
        for item in items:
            item.setdefault("username", user)
            item.setdefault("device", device)
        return items

    def fetch_locations_all_devices(
        self,
        start: datetime,
        end: datetime,
        user: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for device in self.list_devices(user=user):
            items.extend(self.fetch_locations(start, end, device, user=user))
        items.sort(key=lambda x: x["tst"])
        return items

    def save_locations_to_database(
        self,
        session: Optional[Session] = None,
        days_back: int = 7,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Mirror recent fixes from the recorder into the database.

        Existing rows are left alone: the recorder is append-only and can emit
        two records with the same timestamp and position but different trigger,
        which the (username, device, tst) unique constraint collapses.
        """
        if session is None:
            session = self.new_session()
        if end is None:
            end = pendulum.now(tz="UTC")
        if start is None:
            start = pendulum.instance(end).subtract(days=days_back)
        logger.info(
            f"getting OwnTracks locations from {start} to {end} and saving to database"
        )
        items = self.fetch_locations_all_devices(start, end)
        if not items:
            logger.info("no OwnTracks locations returned for this range")
            return 0

        # one query for the whole window, rather than one per point
        existing = set(
            session.exec(
                select(
                    OwnTracksLocation.username,
                    OwnTracksLocation.device,
                    OwnTracksLocation.tst,
                )
                .where(OwnTracksLocation.tst >= pendulum.instance(start).in_timezone("UTC"))
                .where(OwnTracksLocation.tst <= pendulum.instance(end).in_timezone("UTC"))
            ).all()
        )
        # sqlite gives back naive datetimes; compare on naive UTC
        existing = {(u, d, t.replace(tzinfo=None)) for u, d, t in existing}

        num_added = 0
        seen = set()
        for item in items:
            row = OwnTracksLocation.from_api_response(item)
            key = (row.username, row.device, row.tst.replace(tzinfo=None))
            if key in existing or key in seen:
                continue
            seen.add(key)
            session.add(OwnTracksLocation(**row.model_dump()))
            num_added += 1
        logger.info(f"adding {num_added} new rows (in owntrackslocation) to database")
        session.commit()
        return num_added

    def get_locations_for_day(
        self, dt: datetime, session: Optional[Session] = None
    ) -> List[OwnTracksLocation]:
        """Get the location fixes for a given (local) day from the database."""
        if session is None:
            session = self.new_session()
        dt = pendulum.instance(dt)
        start = dt.start_of("day").in_timezone("UTC")
        end = dt.end_of("day").in_timezone("UTC")
        stmt = (
            select(OwnTracksLocation)
            .where(OwnTracksLocation.tst >= start)
            .where(OwnTracksLocation.tst <= end)
            .order_by(OwnTracksLocation.tst)
        )
        return list(session.exec(stmt).all())
