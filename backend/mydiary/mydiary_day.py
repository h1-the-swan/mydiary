from re import S
from typing import Any, List, Dict, Tuple, Union, Optional
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
    Tag,
    JoplinNote,
)
from .markdown_edits import MarkdownDoc
from .db import Session, engine, select

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
        tags: List[Tag] = [],
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
        self.tags = tags
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

    def get_joplin_note_id(self) -> Union[str, None]:
        from .joplin_connector import MyDiaryJoplin

        logger.debug("starting get_joplin_note_id")

        if isinstance(self.joplin_connector, MyDiaryJoplin):
            self.joplin_note_id = self.joplin_connector.get_note_id_by_date(self.dt)
        else:
            with MyDiaryJoplin() as mj:
                self.joplin_note_id = mj.get_note_id_by_date(self.dt)
        logger.debug(f"returning note_id: {self.joplin_note_id}")
        return self.joplin_note_id

    def init_markdown(self) -> str:
        # md_template = "# {dt}\n\n## Words\n\n## Images\n\n## Google Calendar events\n\n{google_calendar_events}\n\n## Pocket articles\n\n{pocket_articles}\n\n## Spotify tracks\n\n{spotify_tracks}\n\n"
        google_calendar_events = self.google_calendar_events_markdown()
        spotify_tracks = self.spotify_tracks_markdown(timezone=self.dt.timezone)
        dt_string = self.dt.to_formatted_date_string()
        md = f"# {dt_string}\n\n"
        md += f"timezone: {self.dt.timezone_name}\n\n"
        md += f"## Words\n\n"
        if self.words and self.words.txt:
            md += f"{self.words.txt}\n\n"
        md += f"## Images\n\n"
        if self.images:
            md += f"{self.images_markdown()}\n\n"
        # only days with location data get a Location section, the same way the
        # Pocket section is omitted once there is nothing to put in it
        if self.owntracks_locations:
            md += f"## Location\n\n{self.owntracks_markdown()}\n\n"
        md += f"## Google Calendar events\n\n{google_calendar_events}\n\n"
        # Pocket is defunct: entries after the latest Pocket item in the
        # database no longer get a Pocket articles section
        from .pocket_connector import get_pocket_section_cutoff

        if self.dt.start_of("day") <= get_pocket_section_cutoff():
            pocket_articles = self.pocket_articles_markdown()
            md += f"## Pocket articles\n\n{pocket_articles}\n\n"
        md += f"## Spotify tracks\n\n{spotify_tracks}\n\n"
        return md

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

    def update_joplin_note(self, session: Session, joplin_connector=None):
        from .joplin_connector import MyDiaryJoplin

        if joplin_connector is not None:
            self.joplin_connector = joplin_connector
        if not isinstance(self.joplin_connector, MyDiaryJoplin):
            raise RuntimeError("need to supply a Joplin connector instance")
        if self.joplin_note_id is None:
            self.get_joplin_note_id()
        if self.joplin_note_id == "does_not_exist":
            raise RuntimeError(
                f"Joplin note does not already exist for date {self.dt.to_date_string()}!"
            )

        note = self.joplin_connector.get_note(self.joplin_note_id)
        md_note = MarkdownDoc(note.body, parent=note)
        md_new = MarkdownDoc(self.init_markdown())

        need_to_update = False
        for sec in md_note.sections:
            try:
                update_txt = md_new.get_section_by_title(sec.title).txt
            except KeyError:
                logger.debug(f"section {sec.title} not found in new text. skipping")
                continue
            result = sec.update(update_txt)
            if result == "updated":
                need_to_update = True
            logger.debug(f"section {sec.title}: {result}")

        if need_to_update is True:
            logger.info(f"updating note: {note.title}")
            r_put_note = self.joplin_connector.update_note_body(note.id, md_note.txt)
            logger.info(f"done. status code: {r_put_note.status_code}")
            self.save_note_and_words_to_db(session=session)

        else:
            logger.info("no updates made")

    def init_joplin_note(
        self, session: Session, joplin_connector=None, body: str = None
    ):
        from .joplin_connector import MyDiaryJoplin

        logger.debug("starting init_joplin_note")
        if joplin_connector is not None:
            self.joplin_connector = joplin_connector
        if not isinstance(self.joplin_connector, MyDiaryJoplin):
            raise RuntimeError("need to supply a Joplin connector instance")
        if self.joplin_note_id is None:
            self.get_joplin_note_id()
        if self.joplin_note_id != "does_not_exist":
            raise RuntimeError(
                f"Joplin note already exists for date {self.dt.to_date_string()} (note id: {self.joplin_note_id})!"
            )

        title = self.dt.strftime("%Y-%m-%d")
        logger.debug("initializing markdown")
        if body is None:
            body = self.init_markdown()
        subfolder_title = str(self.dt.year)
        subfolder_id = self.joplin_connector.get_subfolder_id(
            subfolder_title, create_if_not_exists=True
        )
        logger.info(f"creating note: {title}")
        r_post_note = self.joplin_connector.post_note(
            title=title, body=body, parent_id=subfolder_id
        )
        logger.info(f"done. status code: {r_post_note.status_code}")

        # fill in the note id
        self.get_joplin_note_id()

        self.save_note_and_words_to_db(session=session)

    def init_or_update_joplin_note(
        self, joplin_connector=None, session: Optional[Session] = None
    ):
        from .joplin_connector import MyDiaryJoplin

        if joplin_connector is not None:
            self.joplin_connector = joplin_connector
        if session is None:
            session = Session(engine)
        if not isinstance(self.joplin_connector, MyDiaryJoplin):
            raise RuntimeError("need to supply a Joplin connector instance")
        if self.joplin_note_id is None:
            self.get_joplin_note_id()

        if self.joplin_note_id == "does_not_exist":
            self.init_joplin_note(session=session)
        elif self.joplin_note_id:
            self.update_joplin_note(session=session)
        else:
            # this should not happen
            raise RuntimeError(
                f"error when checking if Joplin note already exists (date: {self.dt}"
            )

    def save_note_and_words_to_db(self, session: Session):
        note = self.joplin_connector.get_note(self.joplin_note_id)
        note.time_last_api_sync = pendulum.now(tz="UTC")
        if note.md_note.get_section_by_title("words").get_content():
            note.words = MyDiaryWords.from_joplin_note(note)
        session.merge(note)
        session.commit()
