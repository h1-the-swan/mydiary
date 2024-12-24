from re import S
from typing import Any, List, Dict, Tuple, Union, Optional
from enum import Enum, IntEnum
from requests import Response
import json
from google.auth.transport import requests
import pendulum
from sqlmodel import Field, Relationship, SQLModel
from pydantic import validator, PrivateAttr
from datetime import datetime, date
from pendulum import now
from pathlib import Path

from sqlalchemy import event, UniqueConstraint
from sqlalchemy.orm import reconstructor

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


def make_markdown_table_header(columns: List[str]) -> str:
    sep = " | "
    header = sep.join(columns)
    header_sep = sep.join(["---"] * len(columns))
    return "\n".join([header, header_sep])


class SpotifyTrackBase(SQLModel):
    spotify_id: str = Field(primary_key=True)
    name: str = Field(index=True)
    artist_name: str = Field(index=True)
    uri: str = Field(index=True)

    @staticmethod
    def parse_track(t: Dict) -> Dict:
        # Parse a spotify track from the Spotify API
        if "track" in t:
            track_data = t["track"]
        else:
            track_data = t
        return {
            "track_id": track_data["id"],
            "track_name": track_data["name"],
            "track_artist": ", ".join(
                [artist["name"] for artist in track_data["artists"]]
            ),
            "track_uri": track_data["uri"],
        }

    @classmethod
    def from_spotify_track(cls, t: Dict) -> "SpotifyTrack":
        track_data = cls.parse_track(t)
        return cls(
            spotify_id=track_data["track_id"],
            name=track_data["track_name"],
            artist_name=track_data["track_artist"],
            uri=track_data["track_uri"],
        )

    def update_track_data(self, t: Dict) -> "SpotifyTrack":
        track_data = self.parse_track(t)
        # self.spotify_id=track_data["track_id"],
        self.name = track_data["track_name"]
        self.artist_name = track_data["track_artist"]
        self.uri = track_data["track_uri"]
        return self


class SpotifyTrack(SpotifyTrackBase, table=True):
    track_history: List["SpotifyTrackHistory"] = Relationship(back_populates="track")


class SpotifyContextTypeEnum(IntEnum):
    album = 0
    playlist = 1
    artist = 2


class SpotifyTrackHistoryBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    played_at: datetime = Field(index=True)  # stored in the database in UTC timezone
    context_uri: Optional[str] = Field(default=None, index=True)
    context_name: Optional[str] = Field(default=None, index=True)
    # context_type: Optional[SpotifyContextTypeEnum]
    context_type: Optional[int] = Field(default=None)

    spotify_id: str = Field(foreign_key="spotifytrack.spotify_id", index=True)

    @classmethod
    def from_spotify_track(cls, t: Dict) -> "SpotifyTrackHistoryBase":
        # Parse a spotify track from the Spotify API
        played_at = t.get("played_at", None)
        if played_at is not None:
            played_at = pendulum.parse(played_at)
        if "track" in t:
            track_data = t["track"]
        else:
            track_data = t
        track_id = track_data["id"]
        track_context = t.get("context", None)
        context_uri = track_context["uri"] if track_context else None
        return cls(
            spotify_id=track_id,
            played_at=played_at,
            context_uri=context_uri,
        )


class SpotifyTrackHistory(SpotifyTrackHistoryBase, table=True):
    __table_args__ = (
        UniqueConstraint("spotify_id", "played_at", name="uix_track_datetime"),
    )
    track: SpotifyTrack = Relationship(
        back_populates="track_history", sa_relationship_kwargs={"lazy": "joined"}
    )


class SpotifyTrackHistoryFrozen(SQLModel):
    id: int
    played_at: datetime
    context_uri: Optional[str]
    context_name: Optional[str]
    # context_type: Optional[SpotifyContextTypeEnum]
    context_type: Optional[int]
    track: SpotifyTrack

    def to_markdown(self, timezone=None) -> str:
        if self.played_at:
            played_at = pendulum.instance(self.played_at)
            if timezone:
                played_at = played_at.in_timezone(timezone)
            played_at = f"{played_at:%H:%M:%S}"
        else:
            played_at = ""

        if self.context_uri:
            context = f"[{self.context_name}]({self.context_uri})"
        else:
            context = ""
        return f"[{self.track.name}]({self.track.uri}) | {self.track.artist_name} | {played_at} | {context}"


# class SpotifyTrackHistory(SQLModel):
#     __table_args__ = (UniqueConstraint('spotify_id', 'played_at', name="uix_track_datetime"),)
#     id: Optional[int] = Field(default=None, primary_key=True)
#     spotify_id: str
#     played_at: datetime


class PerformSongBase(SQLModel):
    name: str = Field(index=True)
    artist_name: Optional[str] = Field(default=None, index=True)
    learned: bool = Field(default=True, index=True)
    spotify_id: Optional[str] = Field(
        foreign_key="spotifytrack.spotify_id", default=None, index=True
    )
    notes: Optional[str] = Field(default=None)
    perform_url: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None, index=True)
    key: Optional[str] = Field(default=None, index=True)  # musical key of the song
    capo: Optional[int] = Field(default=None, index=True)  # fret of capo (0 if no capo)
    lyrics: Optional[str] = Field(default=None)
    learned_dt: Optional[datetime] = Field(default=None, index=True)


class PerformSong(PerformSongBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class PocketArticleTagLink(SQLModel, table=True):
    article_id: int = Field(foreign_key="pocketarticle.id", primary_key=True)
    tag_name: str = Field(foreign_key="tag.name", primary_key=True)


class PocketStatusEnum(IntEnum):
    UNREAD = 0
    ARCHIVED = 1
    SHOULD_BE_DELETED = 2


class PocketArticleBase(SQLModel):
    given_title: str = Field(index=True)
    resolved_title: str = Field(index=True)
    url: str
    favorite: bool = Field(index=True)
    status: PocketStatusEnum = Field(index=True)
    time_added: Optional[datetime] = Field(default=None, index=True)
    time_updated: Optional[datetime] = Field(default=None, index=True)
    time_read: Optional[datetime] = Field(default=None, index=True)
    time_favorited: Optional[datetime] = Field(default=None, index=True)
    listen_duration_estimate: Optional[int] = Field(default=None, index=True)
    word_count: Optional[int] = Field(default=None, index=True)
    top_image_url: Optional[str] = Field(default=None)
    raindrop_id: Optional[int] = Field(default=None, index=True)
    time_pocket_raindrop_sync: Optional[datetime] = Field(default=None, index=True)
    time_last_api_sync: Optional[datetime] = Field(default=None, index=True)

    # private attribute -- will not be included in the database table
    _pocket_item: Optional[Dict] = PrivateAttr()
    # _pocket_tags: Optional[List[str]] = PrivateAttr()

    @property
    def pocket_url(self) -> str:
        return f"https://getpocket.com/read/{self.id}"

    def collect_tags(self, session: Optional["Session"] = None, commit=True):
        # TODO: This doesn't work. Fix it.
        from .pocket_connector import MyDiaryPocket

        return MyDiaryPocket().collect_tags(
            self, self._pocket_tags, session=session, commit=commit
        )

    def to_markdown(self) -> str:
        if self.resolved_title:
            title = self.resolved_title
        elif self.given_title:
            title = self.given_title
        else:
            title = "Unknown title"
        pocket_link = f"[Pocket link]({self.pocket_url})"
        return f"[{title}]({self.url}) ({pocket_link})"


class PocketArticle(PocketArticleBase, table=True):
    id: int = Field(primary_key=True)

    tags: List["Tag"] = Relationship(
        back_populates="pocket_articles",
        link_model=PocketArticleTagLink,
        sa_relationship_kwargs={"cascade": "save-update,merge"},
    )

    @classmethod
    def from_pocket_item(cls, item: Dict) -> "PocketArticle":
        # Parse a Pocket article from the Pocket API
        id = item["item_id"]
        given_title = item.get("given_title", "")
        resolved_title = item.get("resolved_title", "")
        url = item.get("resolved_url", "")
        favorite = bool(int(item.get("favorite", "0")))
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
        top_image_url = item.get("top_image_url", None)
        _pocket_tags = []
        for t in item.get("tags", {}).values():
            tag_name = t["tag"]
            _pocket_tags.append(Tag(name=tag_name, is_pocket_tag=True))
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
            top_image_url=top_image_url,
            tags=_pocket_tags,
        )
        ret._pocket_item = item
        # ret._pocket_tags = _pocket_tags
        return ret


class GoogleCalendarEvent(SQLModel, table=True):
    id: str = Field(primary_key=True)
    summary: str = Field(index=True)
    location: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = Field(default=None)
    start: datetime = Field(index=True)
    end: datetime = Field(index=True)
    start_timezone: str
    end_timezone: str
    time_last_api_sync: Optional[datetime] = Field(default=None, index=True)
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
        summary = event.get("summary", None)
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
    def get_datetime_or_date(self, obj: Dict) -> pendulum.DateTime:
        tz = obj.get("timeZone", "local")
        if "dateTime" in obj:
            return pendulum.parse(obj["dateTime"]).in_timezone(tz=tz)
        elif "date" in obj:
            return pendulum.parse(obj["date"]).in_timezone(tz=tz)
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

    @property
    def md_note(self):
        from .markdown_edits import MarkdownDoc

        return MarkdownDoc(self.body, parent=self)


class TagBase(SQLModel):
    name: str = Field(primary_key=True)
    is_pocket_tag: bool = Field(index=True, default=False)


class Tag(TagBase, table=True):
    pocket_articles: List[PocketArticle] = Relationship(
        back_populates="tags", link_model=PocketArticleTagLink
    )


class TimeZoneChange(SQLModel, table=True):
    changed_at: datetime = Field(primary_key=True)  # in UTC
    tz_before: str
    tz_after: str


class MyDiaryImageBase(SQLModel):
    hash: str = Field(index=True)
    name: Optional[str] = None
    filepath: Optional[str] = None
    nextcloud_path: Optional[str] = None
    description: Optional[str] = None
    thumbnail_size: int
    joplin_resource_id: Optional[str] = Field(index=True, default=None)
    created_at: datetime = Field(index=True)  # stored in the database in UTC timezone


class MyDiaryImage(MyDiaryImageBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class MyDiaryDay(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    dt: datetime = now(tz="America/New_York").start_of("day")
    tags: List[Tag] = []
    diary_txt: str = ""  # Markdown text
    joplin_connector: Any = Field(None, exclude=True)
    joplin_note_id: str = None
    thumbnail: MyDiaryImage = None
    images: List[MyDiaryImage] = []
    spotify_tracks: List[SpotifyTrackHistoryFrozen] = (
        []
    )  # Spotify songs played on this day
    pocket_articles: Dict[str, List[PocketArticle]] = (
        {}
    )  # interactions with Pocket articles on this day
    google_calendar_events: List[GoogleCalendarEvent] = []
    rating: Optional[int] = Field(default=None)
    # (emotional) rating for the day. should it be an enum? should it also include a text description (and be its own object type)?
    flagged: bool = (
        False  # flagged for inspection, in the case of some potential problem
    )

    @classmethod
    def from_dt(
        cls, dt: datetime = now().start_of("day"), spotify_sync: bool = True, **kwargs
    ) -> "MyDiaryDay":
        from .pocket_connector import MyDiaryPocket
        from .spotify_connector import MyDiarySpotify
        from .googlecalendar_connector import MyDiaryGCal

        # from .habitica_connector import MyDiaryHabitica

        mydiary_pocket = MyDiaryPocket()
        pocket_articles = mydiary_pocket.get_articles_for_day(dt)
        # mydiary_pocket.save_articles_to_database(pocket_articles)

        mydiary_spotify = MyDiarySpotify()
        if spotify_sync is True:
            mydiary_spotify.save_recent_tracks_to_database()
        spotify_tracks = mydiary_spotify.get_tracks_for_day(dt)

        mydiary_gcal = MyDiaryGCal()
        google_calendar_events = mydiary_gcal.get_events_for_day(dt)
        mydiary_gcal.save_events_to_database(google_calendar_events)

        # DEPRECATED: I stopped using Habitica
        # # TODO: figure out how to actually use the Habitica data instead of just saving it
        # mydiary_habitica = MyDiaryHabitica()
        # habitica_data = mydiary_habitica.get_user_data()
        # # check if there is any new data
        # habitica_files = list(Path("mydiary/habitica_backups").glob('habitica_userdata*.json'))
        # habitica_files.sort(reverse=True)
        # habitica_most_recent = json.loads(habitica_files[0].read_text())
        # if not mydiary_habitica.iseq_user_data(habitica_most_recent, habitica_data):
        #     outfile = Path("mydiary/habitica_backups").joinpath(
        #         f"habitica_userdata_{pendulum.now():%Y%m%dT%H%M%S}.json"
        #     )
        #     logger.info(f"saving Habitica userdata to {outfile}")
        #     outfile.write_text(json.dumps(habitica_data))

        return cls(
            dt=dt,
            pocket_articles=pocket_articles,
            spotify_tracks=spotify_tracks,
            google_calendar_events=google_calendar_events,
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

    def update_joplin_note(self, joplin_connector=None):
        from .joplin_connector import MyDiaryJoplin
        from .markdown_edits import MarkdownDoc

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

        else:
            logger.info("no updates made")

    def init_joplin_note(self, joplin_connector=None):
        from .joplin_connector import MyDiaryJoplin
        from .markdown_edits import MarkdownDoc

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
        body = self.init_markdown()
        subfolder_title = str(self.dt.year)
        subfolder_id = self.joplin_connector.get_subfolder_id(subfolder_title)
        if subfolder_id is None:
            logger.info(f'"{subfolder_title}" subfolder (subnotebook) not found.')
            logger.info(f'creating subfolder "{subfolder_title}"')
            r_create_subfolder = self.joplin_connector.create_subfolder(subfolder_title)
            r_create_subfolder.raise_for_status()
            logger.debug(f"created subfolder. response: {r_create_subfolder.json()}")
            subfolder_id = r_create_subfolder.json()["id"]
        logger.info(f"creating note: {title}")
        r_post_note = self.joplin_connector.post_note(
            title=title, body=body, parent_id=subfolder_id
        )
        logger.info(f"done. status code: {r_post_note.status_code}")

        # fill in the note id
        self.get_joplin_note_id()

    def init_or_update_joplin_note(self, joplin_connector=None):
        from .joplin_connector import MyDiaryJoplin
        from .markdown_edits import MarkdownDoc

        if joplin_connector is not None:
            self.joplin_connector = joplin_connector
        if not isinstance(self.joplin_connector, MyDiaryJoplin):
            raise RuntimeError("need to supply a Joplin connector instance")
        if self.joplin_note_id is None:
            self.get_joplin_note_id()

        if self.joplin_note_id == "does_not_exist":
            self.init_joplin_note()
        elif self.joplin_note_id:
            self.update_joplin_note()
        else:
            # this should not happen
            raise RuntimeError(
                f"error when checking if Joplin note already exists (date: {self.dt}"
            )


class DogBase(SQLModel):
    name: str = Field(index=True)
    how_met: Optional[str] = Field(default=None, index=True)
    when_met: Optional[datetime] = Field(default=None, index=True)
    owners: Optional[str] = Field(default=None)
    # images: List[MyDiaryImage] = []
    estimated_bday: Optional[datetime] = Field(default=None, index=True)
    notes: Optional[str] = Field(default=None)


class Dog(DogBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class GooglePhotosThumbnail(SQLModel):
    baseUrl: str
    width: int
    height: int


class RecipeTagLink(SQLModel, table=True):
    recipe_id: int = Field(foreign_key="recipe.id", primary_key=True)
    tag_name: str = Field(foreign_key="tag.name", primary_key=True)


class RecipeBase(SQLModel):
    name: str = Field(index=True)
    upvotes: int = Field(default=0, index=True)
    notes: Optional[str] = None


class Recipe(RecipeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # tags: List["Tag"] = Relationship(back_populates="recipes", link_model=RecipeTagLink)
    tags: List["Tag"] = Relationship(link_model=RecipeTagLink)

    recipe_events: Optional[List["RecipeEvent"]] = Relationship(back_populates="recipe")


class RecipeEventBase(SQLModel):
    timestamp: int = Field(index=True)
    notes: Optional[str] = Field(default=None)

    recipe_id: int = Field(foreign_key="recipe.id", index=True)


class RecipeEvent(RecipeEventBase, table=True):
    __table_args__ = (
        UniqueConstraint("recipe_id", "timestamp", name="uix_recipe_timestamp"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe: Recipe = Relationship(back_populates="recipe_events")
