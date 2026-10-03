# -*- coding: utf-8 -*-
"""Source Sync: copy each Source's latest data for a day into the database
(see CONTEXT.md). Every Source runs, and each fails on its own: the report
says which failed and why, and what the others saved stays saved.

Nothing here touches a Diary Note. Reading the day back from the database
is `MyDiaryDay.from_dt`."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional, Protocol

from .db import Session
from .googlecalendar_connector import CalendarSource, save_calendar_day

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

GOOGLE_CALENDAR = "Google Calendar"


class SpotifySource(Protocol):
    """What a Source Sync needs from Spotify (`MyDiarySpotify`)."""

    def save_recent_tracks_to_database(
        self, session: Optional[Session] = None
    ) -> int: ...


class OwnTracksSource(Protocol):
    """What a Source Sync needs from the OwnTracks recorder
    (`MyDiaryOwnTracks`)."""

    def save_locations_to_database(self, session: Optional[Session] = None) -> int: ...


def _spotify() -> SpotifySource:
    import spotipy

    from .spotify_connector import MyDiarySpotify

    # retries off: urllib3 honors Retry-After, so a rate-limited call would
    # otherwise hold the sync (and the request waiting on it) open
    return MyDiarySpotify(spotipy.Spotify(retries=0, status_retries=0))


def _google_calendar() -> CalendarSource:
    from .googlecalendar_connector import MyDiaryGCal

    return MyDiaryGCal()


def _owntracks() -> OwnTracksSource:
    from .owntracks_connector import MyDiaryOwnTracks

    return MyDiaryOwnTracks()


@dataclass
class SourceStatus:
    source: str
    ok: bool
    error: Optional[str] = None  # why it failed, for the diarist to read


class SourceSyncFailed(Exception):
    """A Source the caller can't do without failed to sync."""

    def __init__(self, status: "SourceStatus") -> None:
        self.status = status
        super().__init__(f"{status.source} is unavailable: {status.error}")


@dataclass
class SourceSyncReport:
    statuses: List[SourceStatus] = field(default_factory=list)

    @property
    def failed(self) -> List[SourceStatus]:
        return [s for s in self.statuses if not s.ok]

    def require(self, *sources: str) -> None:
        """Raise `SourceSyncFailed` if any of `sources` failed."""
        for status in self.failed:
            if status.source in sources:
                raise SourceSyncFailed(status)


def _describe(e: Exception) -> str:
    # the type matters as much as the message: a KeyError's message is only
    # the missing key
    return f"{type(e).__name__}: {e}" if str(e) else type(e).__name__


def sync_sources(
    session: Session,
    dt: datetime,
    spotify: Callable[[], SpotifySource] = _spotify,
    gcal: Callable[[], CalendarSource] = _google_calendar,
    owntracks: Callable[[], OwnTracksSource] = _owntracks,
) -> SourceSyncReport:
    """Source Sync of every Source for the day of `dt` (in `dt`'s zone).

    Spotify and OwnTracks sync what they have recently (Spotify's recently
    played list, the recorder's last days), which adds nothing for an older
    day; Google Calendar syncs the day itself. Each argument builds its
    Source's client, so a client that can't be set up (an expired token,
    say) fails that Source alone. Never raises for a Source's failure.

    Each Source commits `session`, and a failed one rolls it back, so call
    this with nothing pending in `session`."""

    def run_spotify() -> None:
        spotify().save_recent_tracks_to_database(session=session)

    def run_google_calendar() -> None:
        calendar = gcal()
        save_calendar_day(session, dt, calendar.get_day(dt), calendar)

    def run_owntracks() -> None:
        owntracks().save_locations_to_database(session=session)

    report = SourceSyncReport()
    for name, run in (
        ("Spotify", run_spotify),
        (GOOGLE_CALENDAR, run_google_calendar),
        ("OwnTracks", run_owntracks),
    ):
        try:
            run()
        except Exception as e:
            # logged in full: this also catches a bug in our own parsing,
            # which the message alone would blame on the Source
            logger.exception(f"{name} sync failed")
            session.rollback()
            report.statuses.append(SourceStatus(name, ok=False, error=_describe(e)))
        else:
            report.statuses.append(SourceStatus(name, ok=True))
    return report
