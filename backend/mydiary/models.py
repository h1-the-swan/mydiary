from re import S
from typing import Any, List, Dict, Tuple, Union, Optional
from enum import Enum, IntEnum
from requests import Response
import json
import hashlib
import pendulum
from sqlmodel import Field, Relationship, SQLModel
from pydantic import validator, PrivateAttr
from datetime import datetime, date
from pendulum import now
from pathlib import Path

from sqlalchemy import event, UniqueConstraint
from sqlalchemy.orm import reconstructor

from .core import get_hash_from_txt
from .markdown_edits import MarkdownDoc

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
    audio_features: "SpotifyTrackHistoryAudioFeatures" = Relationship(
        back_populates="track"
    )


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


class SpotifyTrackHistoryAudioFeaturesBase(SQLModel):
    spotify_id: str = Field(primary_key=True, foreign_key="spotifytrack.spotify_id")
    acousticness: float = Field(index=True)
    danceability: float = Field(index=True)
    duration_ms: int = Field(index=True)
    energy: float = Field(index=True)
    instrumentalness: float = Field(index=True)
    key: int = Field(
        index=True
    )  # uses standard Pitch Class notation. e.g. 0 = C, 1 = C#/Db, -1 means no key detected
    liveness: float = Field(index=True)
    mode: int = Field(index=True)  # Major is 1, minor is 0
    speechiness: float = Field(index=True)
    tempo: float = Field(index=True)  # in BPM
    time_signature: int = Field(
        index=True
    )  # The time signature ranges from 3 to 7 indicating time signatures of "3/4", to "7/4".
    valence: float = Field(index=True)  # higher values mean happy, cheerful, euphoric
    updated_at: datetime = Field(index=True)  # stored in the database in UTC timezone

    @classmethod
    def from_api_response(cls, resp: Dict | List) -> "SpotifyTrackHistoryAudioFeatures":
        if isinstance(resp, list):
            resp = resp[0]
        spotify_id = resp.get("id")
        resp["spotify_id"] = spotify_id
        return cls(**resp)


class SpotifyTrackHistoryAudioFeatures(
    SpotifyTrackHistoryAudioFeaturesBase, table=True
):
    track: SpotifyTrack = Relationship(
        back_populates="audio_features", sa_relationship_kwargs={"lazy": "joined"}
    )


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

    @property
    def archived(self) -> bool:
        return self.status == PocketStatusEnum.ARCHIVED

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

    @property
    def tags_str(self) -> list[str]:
        return [tag.name for tag in self.tags]

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


class PocketArticleUpdate(SQLModel):
    given_title: Optional[str] = None
    resolved_title: Optional[str] = None
    url: Optional[str] = None
    favorite: Optional[bool] = None
    status: Optional[PocketStatusEnum] = None
    time_added: Optional[datetime] = None
    time_updated: Optional[datetime] = None
    time_read: Optional[datetime] = None
    time_favorited: Optional[datetime] = None
    listen_duration_estimate: Optional[int] = None
    word_count: Optional[int] = None
    top_image_url: Optional[str] = None
    pocket_tags: Optional[List[str]] = None
    raindrop_id: Optional[int] = None
    time_pocket_raindrop_sync: Optional[datetime] = None
    time_last_api_sync: Optional[datetime] = None


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


class JoplinNoteImageLink(SQLModel, table=True):
    joplin_note_id: Optional[str] = Field(
        default=None, foreign_key="joplinnote.id", primary_key=True
    )
    mydiary_image_id: Optional[int] = Field(
        default=None, foreign_key="mydiaryimage.id", primary_key=True
    )
    sequence_num: int = Field(primary_key=True)
    note_title: Optional[str] = Field(default=None, index=True)

    note: "JoplinNote" = Relationship(back_populates="mydiary_image_links")
    mydiary_image: "MyDiaryImage" = Relationship(back_populates="note_links")


class JoplinNoteBase(SQLModel):
    id: str = Field(primary_key=True)
    parent_id: str  # notebook id
    title: str = Field(unique=True)
    body: Optional[str] = None  # in markdown
    created_time: datetime
    updated_time: datetime
    body_hash: Optional[str] = Field(default=None, index=True)
    has_words: bool = Field(default=False, index=True)
    has_images: bool = Field(default=False, index=True)

    @classmethod
    def from_api_response(cls, r: Union[Response, Dict]) -> "JoplinNote":
        if isinstance(r, Response):
            r = r.json()
        body = r.get("body", None)
        body_hash = get_hash_from_txt(body) if body else None
        return cls(
            id=r["id"],
            parent_id=r["parent_id"],
            title=r["title"],
            body=body,
            created_time=datetime.fromtimestamp(r["created_time"] / 1000),
            updated_time=datetime.fromtimestamp(r["updated_time"] / 1000),
            body_hash=body_hash,
        )

    @property
    def md_note(self):
        return MarkdownDoc(self.body, parent=self)


class JoplinNote(JoplinNoteBase, table=True):
    time_last_api_sync: Optional[datetime] = Field(default=None, index=True)

    words: Optional["MyDiaryWords"] = Relationship(back_populates="joplin_note")
    mydiary_image_links: List[JoplinNoteImageLink] = Relationship(back_populates="note")


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
    orig_image_hash: Optional[str] = Field(default=None, index=True)


class MyDiaryImage(MyDiaryImageBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    note_links: List[JoplinNoteImageLink] = Relationship(back_populates="mydiary_image")


class MyDiaryWordsBase(SQLModel):
    # the "Words" section of a diary day entry
    joplin_note_id: Optional[str] = Field(
        default=None, index=True, foreign_key="joplinnote.id"
    )
    note_title: Optional[str] = Field(default=None, index=True)
    txt: str = ""  # in markdown
    created_at: datetime = Field(index=True)  # stored in the database in UTC timezone
    updated_at: datetime = Field(index=True)  # stored in the database in UTC timezone
    hash: str = Field(index=True)


class MyDiaryWords(MyDiaryWordsBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    joplin_note: Optional[JoplinNote] = Relationship(back_populates="words")

    @classmethod
    def from_joplin_note(
        cls, note: JoplinNote, body: Optional[str] = None
    ) -> "MyDiaryWords":
        if body is None:
            body = note.body
        if body is None:
            raise ValueError(
                "body must be specified or JoplinNote instance must have a 'body' value"
            )
        md_note = MarkdownDoc(body)
        txt = md_note.get_section_by_title("words").get_content()
        return cls(
            joplin_note_id=note.id,
            note_title=note.title,
            txt=txt,
            created_at=note.created_time,
            updated_at=note.updated_time,
            hash=get_hash_from_txt(txt),
        )

    @classmethod
    def from_txt(cls, txt: str, title: Optional[str] = None) -> "MyDiaryWords":
        now = pendulum.now().in_timezone("UTC")
        return cls(
            note_title=title,
            txt=txt,
            created_at=now,
            updated_at=now,
            hash=get_hash_from_txt(txt),
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
