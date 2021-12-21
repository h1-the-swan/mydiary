import uuid
from typing import List, Dict, Union, Optional
from enum import Enum, IntEnum
import pendulum
from pydantic import BaseModel, Field
from datetime import datetime, date
from pendulum import now
from pathlib import Path


class SpotifyTrack(BaseModel):
    id: str
    name: str
    artist_name: str
    uri: str
    played_at: datetime = None

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
        return cls(
            id=track_id,
            name=track_name,
            artist_name=track_artist,
            uri=track_uri,
            played_at=played_at,
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


class PocketStatusEnum(IntEnum):
    UNREAD = 0
    ARCHIVED = 1
    SHOULD_BE_DELETED = 2


class PocketArticle(BaseModel):
    id: str
    given_title: str
    resolved_title: str
    url: str
    favorite: bool
    status: PocketStatusEnum
    time_added: datetime = None
    time_updated: datetime = None
    time_read: datetime = None
    time_favorited: datetime = None

    @classmethod
    def from_pocket_item(cls, item: Dict) -> "PocketArticle":
        # Parse a Pocket article from the Pocket API
        id = item["item_id"]
        given_title = item["given_title"]
        resolved_title = item["resolved_title"]
        url = item["resolved_url"]
        favorite = int(item["favorite"])
        status = int(item["status"])
        time_added = (
            datetime.fromtimestamp(int(item["time_added"]))
            if int(item["time_added"]) != 0
            else None
        )
        time_updated = (
            datetime.fromtimestamp(int(item["time_updated"]))
            if int(item["time_updated"]) != 0
            else None
        )
        time_read = (
            datetime.fromtimestamp(int(item["time_read"]))
            if int(item["time_read"]) != 0
            else None
        )
        time_favorited = (
            datetime.fromtimestamp(int(item["time_favorited"]))
            if int(item["time_favorited"]) != 0
            else None
        )
        return cls(
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
        )

    def to_markdown(self) -> str:
        return f"[{self.resolved_title}]({self.url})"


class GoogleCalendarEvent(BaseModel):
    id: str
    summary: str
    location: Optional[str] = None
    description: Optional[str] = None
    start: datetime
    end: datetime
    # what else? canceled/deleted?

    @classmethod
    def from_gcal_api_event(cls, event: Dict) -> "GoogleCalendarEvent":
        # Parse a Google calendar event from the API
        id = event["id"]
        summary = event["summary"]
        location = event.get("location", None)
        description = event.get("description", None)
        start = datetime.fromisoformat(event["start"]["dateTime"])
        end = datetime.fromisoformat(event["end"]["dateTime"])
        return cls(
            id=id,
            summary=summary,
            location=location,
            description=description,
            start=start,
            end=end,
        )

    def to_markdown(self) -> str:
        # header = "Start | End | Summary"
        fmt = "%H:%M:%S"
        return f"{self.start.strftime(fmt)} | {self.end.strftime(fmt)} | {self.summary}"


class Tag(BaseModel):
    uid: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str


class MyDiaryImage(BaseModel):
    uid: uuid.UUID
    hash: bytes
    name: str
    filepath: Union[str, Path]
    description: str = None
    created_at: datetime = None


class MyDiaryDay(BaseModel):
    uid: uuid.UUID = Field(default_factory=uuid.uuid4)
    dt: pendulum.DateTime = now().start_of("day")
    tags: List[Tag] = []
    diary_txt: str = ""  # Markdown text
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
    def from_dt(cls, dt: datetime = now().start_of("day")) -> "MyDiaryDay":
        from .pocket_connector import MyDiaryPocket
        from .spotify_connector import MyDiarySpotify
        from .googlecalendar_connector import MyDiaryGCal

        pocket_articles = MyDiaryPocket().get_articles_for_day(dt)
        spotify_tracks = MyDiarySpotify().get_tracks_for_day(dt)
        google_calendar_events = MyDiaryGCal().get_events_for_day(dt)
        return cls(
            dt=dt,
            pocket_articles=pocket_articles,
            spotify_tracks=spotify_tracks,
            google_calendar_events=google_calendar_events,
        )

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
        header = "Name | Artist | Played At"
        lines = [header, "---- | ---- | ----"]
        for t in self.spotify_tracks:
            lines.append(t.to_markdown(timezone=timezone))
        return "\n".join(lines)

    def google_calendar_events_markdown(self) -> str:
        if not self.google_calendar_events:
            return "None"
        header = "Start | End | Summary"
        lines = [header, "---- | ---- | ----"]
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
