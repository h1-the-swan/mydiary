import uuid
from typing import Any, List, Dict, Tuple, Union, Optional
from enum import Enum, IntEnum
from requests import Response
from google.auth.transport import requests
import pendulum
from sqlmodel import Field, Relationship, SQLModel
from pydantic import validator, PrivateAttr
from datetime import datetime, date
from pendulum import now
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.orm import reconstructor

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


def make_markdown_table_header(columns: List[str]) -> str:
    sep = " | "
    header = sep.join(columns)
    header_sep = sep.join(["---"] * len(columns))
    return "\n".join([header, header_sep])


class SpotifyTrack(SQLModel):
    spotify_id: str = Field(index=True)
    name: str = Field(index=True)
    artist_name: str = Field(index=True)
    uri: str
    played_at: Optional[datetime] = Field(default=None, index=True)  # in UTC
    context_type: Optional[str] = None
    context_uri: Optional[str] = None

    @classmethod
    def from_spotify_track(cls, t: Dict) -> "SpotifyTrack":
        # Parse a spotify track from the Spotify API
        played_at = t.get("played_at", None)
        if "track" in t:
            track_data = t["track"]
        else:
            track_data = t
        track_id = track_data["id"]
        track_name = track_data["name"]
        track_artist = ", ".join([artist["name"] for artist in track_data["artists"]])
        track_uri = track_data["uri"]
        track_context = t.get("context", None)
        context_type = track_context["type"] if track_context else None
        context_uri = track_context["uri"] if track_context else None
        return cls(
            spotify_id=track_id,
            name=track_name,
            artist_name=track_artist,
            uri=track_uri,
            played_at=played_at,
            context_type=context_type,
            context_uri=context_uri,
        )

    def to_markdown(self, timezone=None) -> str:
        if self.played_at:
            played_at = pendulum.instance(self.played_at)
            if timezone:
                played_at = played_at.in_timezone(timezone)
            played_at = f"{played_at : %H:%M:%S}"
        else:
            played_at = ""
        return f"[{self.name}]({self.uri}) | {self.artist_name} | {played_at}"


class PocketArticleTagLink(SQLModel, table=True):
    article_id: str = Field(foreign_key="pocketarticle.id", primary_key=True)
    tag_id: uuid.UUID = Field(foreign_key="tag.uid", primary_key=True)


class PocketStatusEnum(IntEnum):
    UNREAD = 0
    ARCHIVED = 1
    SHOULD_BE_DELETED = 2


class PocketArticle(SQLModel, table=True):
    id: str = Field(primary_key=True)
    given_title: str = Field(index=True)
    resolved_title: str = Field(index=True)
    url: str
    favorite: bool = Field(index=True)
    status: PocketStatusEnum
    time_added: Optional[datetime] = Field(default=None, index=True)
    time_updated: Optional[datetime] = Field(default=None, index=True)
    time_read: Optional[datetime] = Field(default=None, index=True)
    time_favorited: Optional[datetime] = Field(default=None, index=True)
    listen_duration_estimate: Optional[int] = Field(default=None, index=True)
    word_count: Optional[int] = Field(default=None, index=True)
    excerpt: Optional[str] = None
    top_image_url: Optional[str] = None

    # private attribute -- will not be included in the database table
    _pocket_item: Optional[Dict] = PrivateAttr()
    _pocket_tags: Optional[List[Tuple]] = PrivateAttr()

    tags: List["Tag"] = Relationship(
        back_populates="pocket_articles", link_model=PocketArticleTagLink
    )

    @property
    def pocket_url(self) -> str:
        return f"https://getpocket.com/read/{self.id}"

    @classmethod
    def from_pocket_item(cls, item: Dict) -> "PocketArticle":
        # Parse a Pocket article from the Pocket API
        id = item["item_id"]
        given_title = item.get("given_title", "")
        resolved_title = item.get("resolved_title", "")
        url = item.get("resolved_url", "")
        favorite = int(item.get("favorite", "0"))
        status = int(item["status"])
        time_added = (
            datetime.fromtimestamp(int(item["time_added"]))
            if "time_added" in item and int(item["time_added"]) != 0
            else None
        )
        time_updated = (
            datetime.fromtimestamp(int(item["time_updated"]))
            if "time_updated" in item and int(item["time_updated"]) != 0
            else None
        )
        time_read = (
            datetime.fromtimestamp(int(item["time_read"]))
            if "time_read" in item and int(item["time_read"]) != 0
            else None
        )
        time_favorited = (
            datetime.fromtimestamp(int(item["time_favorited"]))
            if "time_favorited" in item and int(item["time_favorited"]) != 0
            else None
        )
        listen_duration_estimate = (
            int(item["listen_duration_estimate"])
            if "listen_duration_estimate" in item
            else None
        )
        word_count = int(item["word_count"]) if "word_count" in item else None
        excerpt = item.get("excerpt", None)
        top_image_url = item.get("top_image_url", None)
        if "tags" in item:
            _pocket_tags = [t["tag"] for t in item["tags"].values()]
        else:
            _pocket_tags = []
        ret = cls(
            id=id,
            given_title=given_title,
            resolved_title=resolved_title,
            url=url,
            favorite=favorite,
            status=status,
            time_added=time_added,
            time_updated=time_updated,
            time_read=time_read,
            time_favorited=time_favorited,
            listen_duration_estimate=listen_duration_estimate,
            word_count=word_count,
            excerpt=excerpt,
            top_image_url=top_image_url,
        )
        ret._pocket_item = item
        ret._pocket_tags = _pocket_tags
        return ret

    def collect_tags(self, session: Optional["Session"] = None):
        from .pocket_connector import MyDiaryPocket

        return MyDiaryPocket().collect_tags(self, self._pocket_tags, session=session)

    def to_markdown(self) -> str:
        if self.resolved_title:
            title = self.resolved_title
        elif self.given_title:
            title = self.given_title
        else:
            title = "Unknown title"
        pocket_link = f"[Pocket link]({self.pocket_url})"
        return f"[{title}]({self.url}) ({pocket_link})"


class GoogleCalendarEvent(SQLModel, table=True):
    id: str = Field(primary_key=True)
    summary: str = Field(index=True)
    location: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = None
    start: pendulum.DateTime = Field(index=True)
    end: pendulum.DateTime = Field(index=True)
    start_timezone: str
    end_timezone: str
    # new_test_col: Optional[str] = Field(default=None)
    # what else? canceled/deleted?

    @reconstructor
    def init_on_load(self):
        # Initialize the dates as pendulum instances in the case where the class is loaded from the database
        if not isinstance(self.start, pendulum.DateTime):
            self.start = pendulum.instance(self.start, tz=self.start_timezone)
        if not isinstance(self.end, pendulum.DateTime):
            self.end = pendulum.instance(self.end, tz=self.end_timezone)

    @classmethod
    def from_gcal_api_event(cls, event: Dict) -> "GoogleCalendarEvent":
        # Parse a Google calendar event from the API
        id = event["id"]
        summary = event["summary"]
        location = event.get("location", None)
        description = event.get("description", None)
        start = cls.get_datetime_or_date(event["start"])
        end = cls.get_datetime_or_date(event["end"])
        return cls(
            id=id,
            summary=summary,
            location=location,
            description=description,
            start=start,
            end=end,
            start_timezone=start.timezone_name,
            end_timezone=end.timezone_name,
        )

    @classmethod
    def get_datetime_or_date(self, obj) -> pendulum.DateTime:
        if "dateTime" in obj:
            return pendulum.parse(obj["dateTime"]).in_timezone(tz=obj["timeZone"])
        elif "date" in obj:
            return pendulum.parse(obj["date"]).in_timezone(tz=obj["timeZone"])
        else:
            raise ValueError(
                f'passed object {obj} does not have key "dateTime" or "date"'
            )

    def to_markdown(self) -> str:
        # header = "Start | End | Summary"
        if not self.start.is_same_day(self.end):
            fmt = "%Y-%m-%d %H:%M:%S"
        else:
            fmt = "%H:%M:%S"
        return f"{self.start.strftime(fmt)} | {self.end.strftime(fmt)} | {self.summary}"


@event.listens_for(GoogleCalendarEvent, "refresh")
def gcal_on_refresh(target: GoogleCalendarEvent, context, attrs):
    # init_on_load() is only called when an instances is created, not refreshed
    # so this will make it run when a refresh happens
    target.init_on_load()


class JoplinFolder(SQLModel):
    """This is actually a notebook. Internally notebooks are called "folders".
    See https://joplinapp.org/api/references/rest_api/
    """

    id: str
    title: str
    created_time: datetime
    updated_time: datetime
    parent_id: str

    @classmethod
    def from_api_response(cls, r: Union[Response, Dict]) -> "JoplinFolder":
        if isinstance(r, Response):
            r = r.json()
        return cls(
            id=r["id"],
            title=r["title"],
            created_time=datetime.fromtimestamp(r["created_time"] / 1000),
            updated_time=datetime.fromtimestamp(r["updated_time"] / 1000),
            parent_id=r["parent_id"],
        )


class JoplinNote(SQLModel):
    id: str
    parent_id: str  # notebook id
    title: str
    body: str  # in markdown
    created_time: datetime
    updated_time: datetime

    @classmethod
    def from_api_response(cls, r: Union[Response, Dict]) -> "JoplinNote":
        if isinstance(r, Response):
            r = r.json()
        return cls(
            id=r["id"],
            parent_id=r["parent_id"],
            title=r["title"],
            body=r["body"],
            created_time=datetime.fromtimestamp(r["created_time"] / 1000),
            updated_time=datetime.fromtimestamp(r["updated_time"] / 1000),
        )


class Tag(SQLModel, table=True):
    # TODO
    uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    # pocket_tag_id: Optional[str] = Field(
    #     default=None, index=True, sa_column_kwargs={"unique": True}
    # )

    pocket_articles: List[PocketArticle] = Relationship(
        back_populates="tags", link_model=PocketArticleTagLink
    )


class MyDiaryImage(SQLModel):
    # TODO: this isn't really implemented currently
    uid: uuid.UUID
    hash: bytes
    name: str
    filepath: Union[str, Path]
    description: str = None
    created_at: datetime = None


class MyDiaryDay(SQLModel):
    uid: uuid.UUID = Field(default_factory=uuid.uuid4)
    dt: pendulum.DateTime = now().start_of("day")
    tags: List[Tag] = []
    diary_txt: str = ""  # Markdown text
    joplin_connector: Any = Field(None, exclude=True)
    joplin_note_id: str = None
    thumbnail: MyDiaryImage = None
    images: List[MyDiaryImage] = []
    spotify_tracks: List[SpotifyTrack] = []  # Spotify songs played on this day
    pocket_articles: Dict[
        str, List[PocketArticle]
    ] = {}  # interactions with Pocket articles on this day
    google_calendar_events: List[GoogleCalendarEvent] = []
    rating: Optional[
        int
    ]  # (emotional) rating for the day. should it be an enum? should it also include a text description (and be its own object type)?
    flagged: bool = (
        False  # flagged for inspection, in the case of some potential problem
    )

    @classmethod
    def from_dt(cls, dt: datetime = now().start_of("day"), **kwargs) -> "MyDiaryDay":
        from .pocket_connector import MyDiaryPocket
        from .spotify_connector import MyDiarySpotify
        from .googlecalendar_connector import MyDiaryGCal

        pocket_articles = MyDiaryPocket().get_articles_for_day(dt)

        mydiary_spotify = MyDiarySpotify()
        mydiary_spotify.save_recent_tracks_to_database()
        spotify_tracks = mydiary_spotify.get_tracks_for_day(dt)

        mydiary_gcal = MyDiaryGCal()
        google_calendar_events = mydiary_gcal.get_events_for_day(dt)
        mydiary_gcal.save_events_to_database(google_calendar_events)

        return cls(
            dt=dt,
            pocket_articles=pocket_articles,
            spotify_tracks=spotify_tracks,
            google_calendar_events=google_calendar_events,
            **kwargs,
        )

    def get_joplin_note_id(self) -> Union[str, None]:
        from .joplin_connector import MyDiaryJoplin

        if isinstance(self.joplin_connector, MyDiaryJoplin):
            self.joplin_note_id = self.joplin_connector.get_note_id_by_date(self.dt)
        else:
            with MyDiaryJoplin() as mj:
                self.joplin_note_id = mj.get_note_id_by_date(self.dt)
        return self.joplin_note_id

    def init_markdown(self) -> str:
        md_template = "# {dt}\n\n## Words\n\n## Images\n\n## Google Calendar events\n\n{google_calendar_events}\n\n## Pocket articles\n\n{pocket_articles}\n\n## Spotify tracks\n\n{spotify_tracks}\n\n"
        google_calendar_events = self.google_calendar_events_markdown()
        pocket_articles = self.pocket_articles_markdown()
        spotify_tracks = self.spotify_tracks_markdown(timezone=self.dt.timezone)
        dt_string = self.dt.to_formatted_date_string()
        return md_template.format(
            dt=dt_string,
            google_calendar_events=google_calendar_events,
            pocket_articles=pocket_articles,
            spotify_tracks=spotify_tracks,
        )

    def spotify_tracks_markdown(self, timezone=None) -> str:
        if not self.spotify_tracks:
            return "None"
        columns = ["Name", "Artists", "Played At"]
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


class Dog(SQLModel, table=True):
    uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
