from re import S
from typing import TYPE_CHECKING, Any, List, Dict, Tuple, Union, Optional
from enum import Enum, IntEnum
from requests import Response
import json
import hashlib
import pendulum
from sqlmodel import Field, Relationship, SQLModel
from datetime import datetime, date
from pendulum import now
from pathlib import Path

from .models import (
    SpotifyTrackHistoryFrozen,
    MyDiaryImage,
    MyDiaryWords,
    OwnTracksDayMap,
    OwnTracksLocation,
    PocketArticle,
    GoogleCalendarEvent,
    JoplinNote,
)
from .db import Session, engine, select

if TYPE_CHECKING:
    from .diary_note import DiaryNote
    from .joplin_port import JoplinPort

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


def make_markdown_table_header(columns: List[str]) -> str:
    sep = " | "
    header = sep.join(columns)
    header_sep = sep.join(["---"] * len(columns))
    return "\n".join([header, header_sep])


class MyDiaryDay:
    def __init__(
        self,
        dt: datetime = now(tz="America/New_York").start_of("day"),
        words: Optional[MyDiaryWords] = None,
        diary_txt: str = "",  # Markdown text
        joplin_connector: Optional[Any] = None,
        joplin_note_id: str = None,
        thumbnail: Optional[MyDiaryImage] = None,
        images: List[MyDiaryImage] = [],
        spotify_tracks: List[
            SpotifyTrackHistoryFrozen
        ] = [],  # Spotify songs played on this day
        pocket_articles: Dict[
            str, List[PocketArticle]
        ] = {},  # interactions with Pocket articles on this day
        google_calendar_events: List[GoogleCalendarEvent] = [],
        owntracks_locations: List[
            OwnTracksLocation
        ] = [],  # location fixes recorded on this day
        owntracks_day_maps: List[
            OwnTracksDayMap
        ] = [],  # the day's rendered maps, ordered by panel
        rating: Optional[
            int
        ] = None,  # (emotional) rating for the day. should it be an enum? should it also include a text description (and be its own object type)?
        flagged: bool = False,  # flagged for inspection, in the case of some potential problem
    ):
        self.dt = pendulum.instance(dt)
        self.words = words
        self.diary_txt = diary_txt
        self.joplin_connector = joplin_connector
        self.joplin_note_id = joplin_note_id
        self.thumbnail = thumbnail
        self.images = images
        self.spotify_tracks = spotify_tracks
        self.pocket_articles = pocket_articles
        self.google_calendar_events = google_calendar_events
        self.owntracks_locations = owntracks_locations
        self.owntracks_day_maps = owntracks_day_maps
        self.rating = rating
        self.flagged = flagged

    @classmethod
    def from_dt(
        cls,
        dt: datetime = now().start_of("day"),
        spotify_sync: bool = True,
        gcal_save: bool = True,
        owntracks_sync: bool = True,
        session: Optional[Session] = None,
        note: Optional[Union[JoplinNote, str]] = None,  # can use note or note_id
        **kwargs,
    ) -> "MyDiaryDay":
        from .pocket_connector import MyDiaryPocket
        from .spotify_connector import MyDiarySpotify
        from .googlecalendar_connector import MyDiaryGCal
        from .owntracks_connector import MyDiaryOwnTracks

        if session is None:
            session = Session(engine)

        dt = pendulum.instance(dt)

        words = session.exec(
            select(MyDiaryWords).where(
                MyDiaryWords.note_title == dt.strftime("%Y-%m-%d")
            )
        ).one_or_none()

        if note is not None and not isinstance(note, JoplinNote):
            note = session.get(JoplinNote, note)
        elif words is not None and words.joplin_note is not None:
            note = words.joplin_note

        images = []
        if note is not None:
            images = [
                link.mydiary_image
                for link in sorted(
                    note.mydiary_image_links, key=lambda link: link.sequence_num
                )
            ]

        mydiary_pocket = MyDiaryPocket()
        pocket_articles = mydiary_pocket.get_articles_for_day(dt, session=session)

        mydiary_spotify = MyDiarySpotify()
        if spotify_sync is True:
            # a Spotify outage / revoked token must not break day assembly
            # (e.g. note init); fall back to whatever is already in the database
            try:
                mydiary_spotify.save_recent_tracks_to_database()
            except Exception as e:
                logger.warning(f"skipping Spotify sync during day assembly: {e}")
        spotify_tracks = mydiary_spotify.get_tracks_for_day(dt, session=session)

        mydiary_gcal = MyDiaryGCal()
        google_calendar_events = mydiary_gcal.get_events_for_day(dt)
        if gcal_save is True:
            mydiary_gcal.save_events_to_database(
                google_calendar_events, session=session
            )

        mydiary_owntracks = MyDiaryOwnTracks()
        if owntracks_sync is True:
            # the recorder being unreachable must not break day assembly; fall
            # back to whatever has already been mirrored into the database
            try:
                mydiary_owntracks.save_locations_to_database(session=session)
            except Exception as e:
                logger.warning(f"skipping OwnTracks sync during day assembly: {e}")
        owntracks_locations = mydiary_owntracks.get_locations_for_day(
            dt, session=session
        )
        owntracks_day_maps = list(
            session.exec(
                select(OwnTracksDayMap)
                .where(OwnTracksDayMap.diary_date == dt.date())
                .order_by(OwnTracksDayMap.panel)
            )
        )

        return cls(
            dt=dt,
            words=words,
            images=images,
            pocket_articles=pocket_articles,
            spotify_tracks=spotify_tracks,
            google_calendar_events=google_calendar_events,
            owntracks_locations=owntracks_locations,
            owntracks_day_maps=owntracks_day_maps,
            joplin_note_id=getattr(note, "id", None),
            **kwargs,
        )

    def _joplin_port(self) -> "JoplinPort":
        """The Joplin this day talks to: `joplin_connector` if it's already a
        port, else the client wrapped in one."""
        from .joplin_connector import MyDiaryJoplin
        from .joplin_port import HttpJoplin, JoplinPort

        if isinstance(self.joplin_connector, MyDiaryJoplin):
            return HttpJoplin(self.joplin_connector)
        if isinstance(self.joplin_connector, JoplinPort):
            return self.joplin_connector
        raise RuntimeError("need to supply a Joplin connector instance")

    def get_joplin_note_id(self) -> Union[str, None]:
        """Look up the day's Diary Note. None if Joplin has none."""
        from .diary_note import DiaryNote
        from .joplin_connector import MyDiaryJoplin
        from .joplin_port import HttpJoplin

        logger.debug("starting get_joplin_note_id")

        if self.joplin_connector is not None:
            diary_note = DiaryNote.find(self._joplin_port(), self.dt)
        else:
            with MyDiaryJoplin() as mj:
                diary_note = DiaryNote.find(HttpJoplin(mj), self.dt)
        self.joplin_note_id = diary_note.id if diary_note is not None else None
        logger.debug(f"returning note_id: {self.joplin_note_id}")
        return self.joplin_note_id

    def init_markdown(self) -> str:
        """The body of a new Diary Note for this day, laid out by the section
        registry."""
        from .diary_note import new_note_body
        from .pocket_connector import get_pocket_section_cutoff

        preamble = f"# {self.dt.to_formatted_date_string()}\n\n"
        preamble += f"timezone: {self.dt.timezone_name}\n\n"
        contents = {
            "Words": self.words.txt if self.words and self.words.txt else "",
            "Images": self.images_markdown() if self.images else "",
            **self.refreshed_sections(),
        }
        # only days with location data get a Location section, the same way the
        # Pocket section is omitted once there is nothing to put in it
        if self.owntracks_locations:
            contents["Location"] = self.owntracks_markdown()
        # Pocket is defunct: entries after the latest Pocket item in the
        # database no longer get a Pocket articles section
        if self.dt.start_of("day") <= get_pocket_section_cutoff():
            contents["Pocket articles"] = self.pocket_articles_markdown()
        return new_note_body(preamble, contents)

    def refreshed_sections(self) -> Dict[str, str]:
        """The App-owned Sections a refresh rewrites, as the day's data now
        has them."""
        return {
            "Google Calendar events": self.google_calendar_events_markdown(),
            "Spotify tracks": self.spotify_tracks_markdown(timezone=self.dt.timezone),
        }

    def images_markdown(self) -> str:
        resource_ids_md = []
        for image in self.images:
            if image.joplin_resource_id:
                resource_ids_md.append(f"![](:/{image.joplin_resource_id})")
        return "\n\n".join(resource_ids_md)

    def build_owntracks_track(self, params=None):
        """The day's processed track, in the day's own timezone.

        Using self.dt's timezone matters: a day spent in Ghent must be binned
        into morning/afternoon/evening by Belgian time, not by the diary's
        default zone.
        """
        from .owntracks_track import build_track, points_from_locations

        points = points_from_locations(
            self.owntracks_locations, timezone=self.dt.timezone_name
        )
        return build_track(points, params)

    def owntracks_markdown(self) -> str:
        # lazily imported: owntracks_maps imports this module
        from .owntracks_maps import panels_for_track, section_content

        if not self.owntracks_locations:
            return "None"
        track = self.build_owntracks_track()
        if track.is_empty():
            return "None"
        # re-derive the panels rather than trusting the stored row count: a day
        # that has already been split into areas must not be flattened back to
        # one map here, or sync_day_map_to_note would see an unchanged hash and
        # leave the note that way
        panels = panels_for_track(track)
        by_panel = {m.panel: m.joplin_resource_id for m in self.owntracks_day_maps}
        resource_ids = [by_panel.get(i) for i in range(len(panels))]
        return section_content(resource_ids, panels)

    def spotify_tracks_markdown(self, timezone=None) -> str:
        if not self.spotify_tracks:
            return "None"
        columns = ["Name", "Artists", "Played At", "Context"]
        header = make_markdown_table_header(columns)
        lines = [header]
        for t in self.spotify_tracks:
            lines.append(t.to_markdown(timezone=timezone))
        return "\n".join(lines)

    def google_calendar_events_markdown(self) -> str:
        if not self.google_calendar_events:
            return "None"
        columns = ["Start", "End", "Summary"]
        header = make_markdown_table_header(columns)
        lines = [header]
        for e in self.google_calendar_events:
            lines.append(e.to_markdown())
        return "\n".join(lines)

    def pocket_articles_markdown(self) -> str:
        if not self.pocket_articles or not any(self.pocket_articles.values()):
            return "None"
        lines = []
        for k, articles in self.pocket_articles.items():
            if articles is not None and len(articles) > 0:
                lines.append(f"{k.title()}:")  # heading
                for a in articles:
                    lines.append(a.to_markdown())
                # add a newline onto the last one in this section
                lines[-1] += "\n"
        return "\n".join(lines)

    def update_joplin_note(self, session: Optional[Session] = None, joplin_connector=None):
        """Refresh the day's Diary Note: replace its Google Calendar events
        and Spotify tracks with the day's data, adding either section if the
        note lacks it. Nothing else in the note is written (ADR-0001)."""
        from .diary_note import DiaryNote

        if joplin_connector is not None:
            self.joplin_connector = joplin_connector
        if session is None:
            session = Session(engine)
        diary_note = DiaryNote.find(self._joplin_port(), self.dt)
        if diary_note is None:
            self.joplin_note_id = None
            raise RuntimeError(
                f"Joplin note does not already exist for date {self.dt.to_date_string()}!"
            )
        self._refresh(session, diary_note)

    def _refresh(self, session: Session, diary_note: "DiaryNote") -> None:
        self.joplin_note_id = diary_note.id
        with diary_note.edit(session) as edit:
            for heading, content in self.refreshed_sections().items():
                edit.set_section(heading, content)
        if edit.wrote:
            logger.info(f"updated note: {self.dt.to_date_string()}")
        else:
            logger.info("no updates made")

    def init_joplin_note(
        self, session: Optional[Session] = None, joplin_connector=None, body: str = None
    ):
        """Create the day's Diary Note from `body`, or from the template if
        none is given, and mirror it."""
        from .diary_note import DiaryNote

        logger.debug("starting init_joplin_note")
        if joplin_connector is not None:
            self.joplin_connector = joplin_connector
        if session is None:
            session = Session(engine)
        joplin = self._joplin_port()
        if body is None:
            logger.debug("initializing markdown")
            body = self.init_markdown()
        logger.info(f"creating note: {self.dt.to_date_string()}")
        diary_note = DiaryNote.create(session, joplin, self.dt, body)
        self.joplin_note_id = diary_note.id

    def init_or_update_joplin_note(
        self, joplin_connector=None, session: Optional[Session] = None
    ):
        from .diary_note import DiaryNote

        if joplin_connector is not None:
            self.joplin_connector = joplin_connector
        if session is None:
            session = Session(engine)
        diary_note = DiaryNote.find(self._joplin_port(), self.dt)
        if diary_note is None:
            self.init_joplin_note(session=session)
        else:
            self._refresh(session, diary_note)
