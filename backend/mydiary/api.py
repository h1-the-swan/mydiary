import os
from datetime import datetime, date
import re
import requests
import io
import json
import pendulum
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import pydantic
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import desc, all_
from sqlalchemy.sql.functions import count
from sqlalchemy.orm import make_transient_to_detached
from sqlmodel import Field, SQLModel

from mydiary.joplin_connector import MyDiaryJoplin
from .db import Session, engine, select, func, get_db_status
from .models import (
    Recipe,
    RecipeBase,
    RecipeEventBase,
    SpotifyTrackBase,
    SpotifyTrackHistoryBase,
    SpotifyTrackHistory,
    PerformSongBase,
    PerformSong,
    DogBase,
    Dog,
    GoogleCalendarEvent,
    PocketStatusEnum,
    SpotifyTrackHistoryFrozen,
    Tag,
    TagBase,
    PocketArticle,
    PocketArticleBase,
    PocketArticleUpdate,
    JoplinNoteImageLink,
    JoplinNote,
    MyDiaryImageBase,
    MyDiaryImage,
    TimeZoneChange,
    SpellingBeeMiss,
    SpellingBeeMissBase,
    SpellingBeePuzzle,
    SpellingBeePuzzleBase,
    SpellingBeeDefinition,
    SpellingBeeDefinitionBase,
)
from .nextcloud_connector import MyDiaryNextcloud
from . import spelling_bee
from .dictionary_connector import fetch_definition
from .spotify_connector import normalize_spotify_id
from .pocket_connector import MyDiaryPocket
from .core import get_last_timezone
from .mydiary_day import MyDiaryDay
import uvicorn

import logging

root_logger = logging.getLogger("uvicorn")
logger = root_logger.getChild(__name__)


class GoogleCalendarEventRead(GoogleCalendarEvent):
    pass


class TagRead(TagBase):
    num_pocket_articles: Optional[int] = None


class PocketArticleRead(PocketArticleBase):
    # tags_: List[TagRead] = Field(alias="tags")
    tags: List[TagRead] = []


class SpotifyTrackHistoryCreate(SpotifyTrackHistoryBase):
    pass


class SpotifyTrackHistoryRead(SpotifyTrackHistoryBase):
    id: int
    track: SpotifyTrackBase


class PerformSongRead(PerformSongBase):
    id: int


class PerformSongCreate(PerformSongBase):
    pass


class PerformSongUpdate(SQLModel):
    name: Optional[str] = None
    artist_name: Optional[str] = None
    learned: Optional[bool] = None
    spotify_id: Optional[str] = None
    notes: Optional[str] = None
    perform_url: Optional[str] = None
    created_at: Optional[datetime] = None
    key: Optional[str] = None
    capo: Optional[int] = None
    lyrics: Optional[str] = None
    learned_dt: Optional[datetime] = None


class MyDiaryImageRead(MyDiaryImageBase):
    id: int


class DogRead(DogBase):
    id: int


class DogCreate(DogBase):
    pass


class DogUpdate(SQLModel):
    name: Optional[str] = None
    how_met: Optional[str] = None
    when_met: Optional[datetime] = None
    owners: Optional[str] = None
    # images: List[MyDiaryImage] = []
    estimated_bday: Optional[datetime] = None
    notes: Optional[str] = None


class RecipeRead(RecipeBase):
    id: int


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(SQLModel):
    name: Optional[str] = None
    upvotes: Optional[int] = None
    notes: Optional[str] = None


class RecipeEventRead(RecipeEventBase):
    id: int


class RecipeEventCreate(RecipeEventBase):
    pass


class RecipeEventUpdate(SQLModel):
    timestamp: Optional[int] = None
    notes: Optional[str] = None
    recipe_id: Optional[int] = None


class SpellingBeeMissRead(SpellingBeeMissBase):
    id: int
    # derived, not stored: a puzzle has exactly seven letters, so any valid
    # word with seven distinct ones is necessarily a pangram
    is_pangram: bool


class SpellingBeeMissUpdate(SQLModel):
    puzzle_date: Optional[date] = None
    word: Optional[str] = None


class SpellingBeeMissBulkCreate(SQLModel):
    # you miss a handful of words per puzzle, so entry is bulk by default
    puzzle_date: date
    words: List[str]
    center_letter: Optional[str] = None
    outer_letters: Optional[str] = None


class SpellingBeeMissBulkResult(SQLModel):
    # these are always sent, so they're required -- an optional list would make
    # every caller in the frontend guard against an undefined that never comes
    puzzle_date: date
    created: List[SpellingBeeMissRead]
    skipped: List[str]  # already recorded for this date
    invalid: List[str]  # too short to be a Bee answer


class SpellingBeeAddPreview(SQLModel):
    """What would happen if these words were added to this date.

    The entry form asks for this before writing, so it can warn about a date
    that already has words and refuse a set that can't be one puzzle.
    """

    puzzle_date: date
    existing_words: List[str]  # already recorded for this date
    new_words: List[str]  # would be added
    duplicate_words: List[str]  # already recorded, would be skipped
    invalid_words: List[str]  # too short to be a Bee answer
    conflict: bool  # existing + new can't be one puzzle
    problems: List[str]
    combined_letters: List[str]
    center_candidates: List[str]
    groups: List[List[str]]  # words split into the puzzles they look like


class SpellingBeePuzzleRead(SpellingBeePuzzleBase):
    puzzle_date: date


class SpellingBeePuzzleUpsert(SQLModel):
    center_letter: str
    outer_letters: str


class SpellingBeeDefinitionRead(SpellingBeeDefinitionBase):
    word: str


class SpellingBeeWordMiss(SQLModel):
    # one occurrence behind a rolled-up word. carries the id so a single day
    # can be removed without deleting the whole word's history.
    id: int
    puzzle_date: date


class SpellingBeeWordRead(SQLModel):
    # one row per distinct word, rolled up across every day you missed it
    word: str
    times_missed: int
    first_missed: date
    last_missed: date
    misses: List[SpellingBeeWordMiss]
    is_pangram: bool
    definition: Optional[str] = None
    part_of_speech: Optional[str] = None


class SpellingBeeHiveRead(SQLModel):
    puzzle_date: date
    center_letter: str
    outer_letters: List[str]
    exact: bool  # False == letters worked out from the words, not recorded
    words: List[str]
    pangrams: List[str]
    warnings: List[str]


def get_session():
    with Session(engine) as session:
        yield session


def get_joplin_client():
    with MyDiaryJoplin(init_config=False) as j:
        yield j


# handler = logging.StreamHandler()
# handler.setFormatter(
#     logging.Formatter(
#         fmt="%(asctime)s %(name)s.%(lineno)d %(levelname)s : %(message)s",
#         datefmt="%H:%M:%S",
#     )
# )
# # root_logger.addHandler(handler)
# # logger.addHandler(handler)
# logging.getLogger("mydiary").addHandler(handler)
# # root_logger.setLevel(logging.DEBUG)
# # logger.setLevel(logging.DEBUG)
# logging.getLogger("mydiary").setLevel(logging.DEBUG)
# logging.getLogger("uvicorn.error").propagate = False
# logger.debug("debug mode is on")
# logger.info("info")
# logger.error("error")
# print('print')


def scheduled_spotify_save_recent_tracks():
    from mydiary.spotify_connector import MyDiarySpotify

    mydiary_spotify = MyDiarySpotify()
    num_saved = mydiary_spotify.save_recent_tracks_to_database(add_or_update_audio_features=False)
    logger.info(f"{num_saved} recent spotify tracks saved")



def scheduled_owntracks_sync():
    from mydiary.owntracks_connector import MyDiaryOwnTracks

    num_saved = MyDiaryOwnTracks().save_locations_to_database()
    logger.info(f"{num_saved} owntracks locations saved")


scheduler = BackgroundScheduler()

apscheduler_logger = logging.getLogger("apscheduler")
apscheduler_logger.setLevel(logging.INFO)
if not apscheduler_logger.handlers:
    apscheduler_handler = logging.StreamHandler()
    apscheduler_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
    )
    apscheduler_logger.addHandler(apscheduler_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # logger.info('lifespan startup!')
    # print('lifespan startup!')
    scheduler.add_job(
        scheduled_spotify_save_recent_tracks,
        CronTrigger.from_crontab("10 * * * *"),
        # sleep/suspend (e.g. WSL2 host sleeping) makes wakeups miss the default
        # 1-second misfire grace time; run the job however late it fires
        misfire_grace_time=None,
    )  # At 10 minutes past the hour
    scheduler.add_job(
        scheduled_owntracks_sync,
        CronTrigger.from_crontab("25 * * * *"),
        misfire_grace_time=None,
    )  # At 25 minutes past the hour
    # nothing writes a map into a note on a schedule: that is a manual action,
    # via the "Add map to note" button or POST /owntracks/map/{dt}/to_note
    # scheduler.add_job(lambda: logger.info("heartbeat"), "interval", minutes=1)
    scheduler.start()
    yield
    from .nextcloud_connector import close_async_client

    await close_async_client()


app = FastAPI(
    lifespan=lifespan,
    title="mydiary",
    root_path="/api",
    openapi_url="/openapi.json",
    debug=True,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])


@app.get("/testhealthcheck", operation_id="testHealthCheck2")
async def testhealthcheck():
    return "hello all good"


@app.get("/db_status", operation_id="dbStatus")
async def db_status(more: bool = False) -> Dict[str, Any]:
    return get_db_status(more=more)


@app.get("/gcal/get_auth_url", operation_id="getGCalAuthUrl", response_model=str)
async def get_gcal_auth_url():
    from mydiary.googlecalendar_connector import MyDiaryGCal

    mydiary_gcal = MyDiaryGCal(init_service=False)
    mydiary_gcal._init_flow()
    return Response(mydiary_gcal.flow.authorization_url()[0])


@app.post("/gcal/refresh_token", operation_id="refreshGCalToken")
async def refresh_gcal_token(code: str):
    from mydiary.googlecalendar_connector import MyDiaryGCal

    mydiary_gcal = MyDiaryGCal(init_service=False)
    mydiary_gcal._init_flow()
    mydiary_gcal.flow.fetch_token(code=code)
    mydiary_gcal._save_token_cache()


@app.post("/gcal/check_auth", operation_id="checkGCalAuth")
async def check_gcal_auth():
    try:
        from mydiary.googlecalendar_connector import MyDiaryGCal

        events = MyDiaryGCal().get_events_for_day(pendulum.today())
        return Response(status_code=200)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=getattr(e, "message", "NO EXCEPTION MESSAGE AVAILABLE"),
        )


@app.get(
    "/gcal/events",
    operation_id="readGCalEvents",
    response_model=List[GoogleCalendarEventRead],
)
def read_gcal_events(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=100),
):
    events = session.exec(select(GoogleCalendarEvent).offset(offset).limit(limit)).all()
    return events


@app.get("/tags", operation_id="readTags", response_model=List[TagRead])
def read_tags(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=1000),
    is_pocket_tag: Optional[bool] = None,
):
    stmt = select(Tag)
    if is_pocket_tag is not None:
        stmt = stmt.where(Tag.is_pocket_tag == is_pocket_tag)
    stmt = stmt.offset(offset).limit(limit)
    tags: List[Tag] = session.exec(stmt).all()
    ret: List[TagRead] = []
    for tag in tags:
        num_pocket_articles = len(tag.pocket_articles)
        item = TagRead.model_validate(tag)
        item.num_pocket_articles = num_pocket_articles
        ret.append(item)
    return ret


@app.get(
    "/pocket/articles/count", operation_id="countPocketArticles", response_model=int
)
def count_pocket_articles(*, session: Session = Depends(get_session)):
    return session.exec(count(PocketArticle.id)).scalar()


@app.get(
    "/pocket/articles",
    operation_id="readPocketArticles",
    response_model=List[PocketArticleRead],
)
def read_pocket_articles(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100),
    status: Optional[Set[int]] = Query(None),
    tags: Optional[str] = Query(None, description="Tag names (comma separated"),
    dateMin: Optional[str] = Query(None),
    dateMax: Optional[str] = Query(None),
    year: Optional[int] = Query(
        None, description="Year added (ignored if dateRange is specified)"
    ),
):
    stmt = (
        select(PocketArticle)
        # .join(PocketArticle.tags, isouter=True)
        .order_by(desc(PocketArticle.time_updated))
    )
    if status is not None:
        stmt = stmt.where(PocketArticle.status.in_([PocketStatusEnum(s) for s in status]))
    if tags:
        for t in tags.split(","):
            stmt = stmt.where(PocketArticle.tags.any(Tag.name == t))

    if dateMin:
        stmt = stmt.where(PocketArticle.time_added >= dateMin)
    if dateMax:
        stmt = stmt.where(PocketArticle.time_added <= dateMax)
    if year is not None and (not dateMin and not dateMax):
        # stmt = stmt.where(PocketArticle.time_added.year==year)
        # The above doesn't work (maybe a SQLite issue?) so do this instead:
        dt = pendulum.datetime(year=year, month=1, day=1)
        stmt = stmt.where(PocketArticle.time_added >= dt.start_of("year"))
        stmt = stmt.where(PocketArticle.time_added < dt.end_of("year"))
    articles = session.exec(stmt.offset(offset).limit(limit)).all()
    return articles


@app.patch(
    "/pocket/articles/{article_id}",
    operation_id="updatePocketArticle",
    response_model=PocketArticleRead,
)
def update_pocket_article(
    *,
    session: Session = Depends(get_session),
    article_id: int,
    article: PocketArticleUpdate,
):
    db_article = session.get(PocketArticle, article_id)
    if not db_article:
        raise HTTPException(status_code=404, detail="PocketArticle not found")
    mydiary_pocket = MyDiaryPocket()
    db_article = mydiary_pocket.update_article(
        db_article=db_article,
        article_update=article,
        session=session,
        post_commit=False,
    )
    session.commit()
    # session.refresh(db_article)
    return db_article


@app.get(
    "/spotify/history",
    operation_id="readSpotifyHistory",
    response_model=List[SpotifyTrackHistoryRead],
)
async def read_spotify_history(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100),
):
    stmt = select(SpotifyTrackHistory).order_by(desc(SpotifyTrackHistory.played_at))
    tracks = session.exec(stmt.offset(offset).limit(limit)).all()
    return tracks


@app.get(
    "/spotify/history/count", operation_id="spotifyHistoryCount", response_model=int
)
async def spotify_history_count(*, session: Session = Depends(get_session)):
    stmt = select(func.count(SpotifyTrackHistory.id))
    return session.exec(stmt).one()


@app.get(
    "/spotify/album_image_url/{track_id}",
    operation_id="getSpotifyImageUrl",
    response_model=str,
)
async def get_spotify_image_url(
    *,
    session: Session = Depends(get_session),
    track_id: Optional[str],
):
    if not track_id:
        return ""
    from mydiary.spotify_connector import MyDiarySpotify

    mydiary_spotify = MyDiarySpotify()
    sp = mydiary_spotify.sp
    track = sp.track(track_id)
    return Response(track["album"]["images"][0]["url"].strip('"'))


@app.post(
    "/spotify/save_recent_tracks_to_database",
    operation_id="spotifySaveRecentTracksToDatabase",
    response_model=int,
)
async def spotify_save_recent_tracks_to_database():
    from mydiary.spotify_connector import MyDiarySpotify

    mydiary_spotify = MyDiarySpotify()
    num_saved = mydiary_spotify.save_recent_tracks_to_database()
    return num_saved


@app.get("/joplin/get_note_id/{dt}", operation_id="joplinGetNoteId", response_model=str)
def joplin_get_note_id(
    dt: str, mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client)
) -> str:
    if dt == "today":
        dt = pendulum.today()
    elif dt == "yesterday":
        dt = pendulum.yesterday()
    else:
        dt = pendulum.parse(dt)
    existing_id = mydiary_joplin.get_note_id_by_date(dt)
    # if existing_id == "does_not_exist":
    #     raise RuntimeError(
    #         f"Joplin note does not already exist for date {dt.to_date_string()}!"
    #     )
    return Response(existing_id)


@app.post(
    "/joplin/init_note/{dt}",
    operation_id="joplinInitNote",
)
async def joplin_init_note(
    dt: str,
    tz: str = "local",
    session: Session = Depends(get_session),
    mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client),
    body: Optional[str] = None,
) -> str:
    if dt == "today":
        dt = pendulum.today(tz=tz)
    elif dt == "yesterday":
        dt = pendulum.yesterday(tz=tz)
    else:
        dt = pendulum.parse(dt, tz=tz)
    try:
        if body:
            # body is supplied, so no need to sync with external APIs
            day = MyDiaryDay.from_dt(
                dt,
                joplin_connector=mydiary_joplin,
                session=session,
                spotify_sync=False,
                gcal_save=False,
            )
        else:
            day = MyDiaryDay.from_dt(
                dt, joplin_connector=mydiary_joplin, session=session
            )
        logger.debug("created MyDiaryDay instance")
        day.init_joplin_note(
            session=session, joplin_connector=mydiary_joplin, body=body
        )
        logger.debug("initialized note")
        return day.joplin_note_id
    except Exception as e:
        # raise HTTPException(status_code=500, detail=getattr(e, 'message', 'NO EXCEPTION MESSAGE AVAILABLE'))
        print(e)
        raise


@app.get("/day_init_markdown/{dt}", operation_id="dayInitMarkdown")
async def day_init_markdown(
    dt: str, tz: str = "local", session: Session = Depends(get_session)
):
    if tz == "infer":
        tz = get_last_timezone(dt, session=session)
        logger.info(f"inferred tz: {tz}")

    if dt == "today":
        dt_obj = pendulum.today(tz=tz)
    elif dt == "yesterday":
        dt_obj = pendulum.yesterday(tz=tz)
    else:
        dt_obj = pendulum.parse(dt, tz=tz)
    logger.info(f"dt_obj tz: {dt_obj.tz}")
    day = MyDiaryDay.from_dt(dt_obj, session=session)
    return day.init_markdown()


@app.get(
    "/joplin/get_note/{note_id}",
    operation_id="joplinGetNote",
    response_model=JoplinNote,
)
def joplin_get_note(
    note_id: str,
    remove_image_refs: bool = False,
    mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client),
):
    note = mydiary_joplin.get_note(note_id)
    if remove_image_refs is True:
        note.body = re.sub(
            r"!\[.*?\]\(:/([a-zA-Z0-9]+?)\)", r"[Joplin resource_id: \1]", note.body
        )
    return note


@app.get(
    "/joplin/get_note_images/{note_id}",
    operation_id="joplinNoteImages",
    response_model=List[MyDiaryImageRead],
)
def joplin_get_note_images(
    note_id: str,
    session: Session = Depends(get_session),
    mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client),
):
    if not note_id or note_id == "does_not_exist":
        return []

    note = mydiary_joplin.get_note(note_id)
    images = [
        session.exec(
            select(MyDiaryImage).where(MyDiaryImage.joplin_resource_id == resource_id)
        ).first()
        for resource_id in note.md_note.get_image_resource_ids()
    ]
    # skip resource ids with no database row (e.g. images added by the removed
    # Google Photos integration)
    return [img for img in images if img is not None]


@app.post(
    "/joplin/update_note/{dt}",
    operation_id="joplinUpdateNote",
)
async def joplin_update_note(
    dt: str,
    tz: str = "local",
    session: Session = Depends(get_session),
    mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client),
):
    if dt == "today":
        dt = pendulum.today(tz=tz)
    elif dt == "yesterday":
        dt = pendulum.yesterday(tz=tz)
    else:
        dt = pendulum.parse(dt, tz=tz)
    try:
        day = MyDiaryDay.from_dt(dt, joplin_connector=mydiary_joplin, session=session)
        logger.debug("created MyDiaryDay instance")
        day.update_joplin_note(session=session, joplin_connector=mydiary_joplin)
        logger.debug("updated note")
    except Exception as e:
        # raise HTTPException(status_code=500, detail=getattr(e, 'message', 'NO EXCEPTION MESSAGE AVAILABLE'))
        print(e)
        raise


@app.get(
    "/joplin/get_info_all_days",
    operation_id="joplinGetInfoAllDays",
    response_model=list,
)
async def joplin_get_info_all_days(
    min_dt: str, max_dt: str, mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client)
):
    return mydiary_joplin.get_info_all_days(
        min_dt=pendulum.parse(min_dt), max_dt=pendulum.parse(max_dt)
    )


# def _modify_filepath(filepath):
#     filepath = filepath.split("/")[-4:]
#     filepath = "/".join(filepath)
#     return filepath


@app.get(
    "/nextcloud/thumbnails/{dt}",
    operation_id="nextcloudPhotosThumbnailUrls",
    response_model=List[str],
)
def nextcloud_photos_thumbnails_url(dt: str):
    if dt == "today":
        dt = pendulum.today()
    elif dt == "yesterday":
        dt = pendulum.yesterday()
    else:
        dt = pendulum.parse(dt)

    mydiary_nextcloud = MyDiaryNextcloud()
    filepaths = mydiary_nextcloud.get_filepaths_for_day(dt)
    # urls = [mydiary_nextcloud.get_image_thumbnail_url(fp) for fp in filepaths]
    # filepaths = [_modify_filepath(filepath) for filepath in filepaths]
    return filepaths


# @app.get(
#     "/nextcloud/thumbnail_dims",
#     operation_id="getNextcloudPhotosThumbnailDims",
#     response_model=Tuple[int, int],
# )
# def get_nextcloud_thumbnail_dims(url: str):
#     if not url:
#         return (0, 0)
#     mydiary_nextcloud = MyDiaryNextcloud()
#     return mydiary_nextcloud.get_image_thumbnail_dimensions(url)


@app.get(
    "/nextcloud/thumbnail_img",
    operation_id="nextcloudThumbnailImg",
    # Set what the media type will be in the autogenerated OpenAPI specification.
    # fastapi.tiangolo.com/advanced/additional-responses/#additional-media-types-for-the-main-response
    responses={200: {"content": {"image/png": {}}}},
)
async def get_nextcloud_image(url: str, request: Request):
    from . import thumbnail_cache

    key = thumbnail_cache.cache_key(url)
    etag = f'"{key}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    image_bytes = thumbnail_cache.get_cached(key)
    if image_bytes is None:
        mydiary_nextcloud = MyDiaryNextcloud()
        image_bytes = await mydiary_nextcloud.aget_image_thumbnail(url)
        thumbnail_cache.store(key, image_bytes)
    return Response(
        content=image_bytes,
        media_type=thumbnail_cache.sniff_media_type(image_bytes),
        headers={
            "ETag": etag,
            "Cache-Control": "private, max-age=31536000, immutable",
        },
    )


def _owntracks_day(dt: str, tz: str, session: Session) -> pendulum.DateTime:
    """Resolve a day string to a timezone-aware start-of-day.

    Defaults to the inferred timezone rather than "local": the container runs on
    UTC, and for a map the day boundary decides what is on it.
    """
    if tz == "infer":
        try:
            tz = get_last_timezone(dt, session=session)
        except (AttributeError, TypeError):
            # no TimeZoneChange rows recorded yet
            logger.warning("could not infer timezone; falling back to local")
            tz = "local"
    if dt == "today":
        return pendulum.today(tz=tz)
    if dt == "yesterday":
        return pendulum.yesterday(tz=tz)
    return pendulum.parse(dt, tz=tz)


def _track_params(
    max_acc: int,
    stay_radius_m: float,
    stay_minutes: float,
    gap_minutes: float,
    gap_metres: float,
    dwell_max_kmh: float,
) -> "TrackParams":
    from .owntracks_track import TrackParams

    return TrackParams(
        max_acc=max_acc,
        stay_radius_m=stay_radius_m,
        stay_minutes=stay_minutes,
        gap_minutes=gap_minutes,
        gap_metres=gap_metres,
        dwell_max_kmh=dwell_max_kmh,
    )


@app.get("/owntracks/locations/{dt}", operation_id="owntracksLocationsForDay")
def owntracks_locations_for_day(
    dt: str, tz: str = "infer", session: Session = Depends(get_session)
):
    """The day's raw location fixes, before any smoothing."""
    from .owntracks_connector import MyDiaryOwnTracks

    dt_obj = _owntracks_day(dt, tz, session)
    locations = MyDiaryOwnTracks().get_locations_for_day(dt_obj, session=session)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [loc.lon, loc.lat]},
                "properties": {
                    "tst": pendulum.instance(loc.tst, tz="UTC")
                    .in_timezone(dt_obj.timezone_name)
                    .isoformat(),
                    "acc": loc.acc,
                    "motion": loc.motion,
                    "trigger": loc.trigger,
                    "device": loc.device,
                },
            }
            for loc in locations
        ],
    }


@app.get("/owntracks/track/{dt}", operation_id="owntracksTrackForDay")
def owntracks_track_for_day(
    dt: str,
    tz: str = "infer",
    max_acc: int = 100,
    stay_radius_m: float = 150.0,
    stay_minutes: float = 20.0,
    gap_minutes: float = 45.0,
    gap_metres: float = 250.0,
    dwell_max_kmh: float = 1.0,
    session: Session = Depends(get_session),
):
    """The processed day: stays and links, as GeoJSON.

    The frontend map draws this, so the interactive view and the rendered PNG
    always agree.
    """
    from .owntracks_connector import MyDiaryOwnTracks
    from .owntracks_track import build_track, points_from_locations, track_to_geojson

    dt_obj = _owntracks_day(dt, tz, session)
    params = _track_params(
        max_acc, stay_radius_m, stay_minutes, gap_minutes, gap_metres, dwell_max_kmh
    )
    locations = MyDiaryOwnTracks().get_locations_for_day(dt_obj, session=session)
    points = points_from_locations(locations, timezone=dt_obj.timezone_name)
    return track_to_geojson(build_track(points, params))


@app.get(
    "/owntracks/map/{dt}.png",
    operation_id="owntracksDayMapImage",
    responses={200: {"content": {"image/png": {}}}},
)
def owntracks_day_map_image(
    dt: str,
    request: Request,
    tz: str = "infer",
    width: int = 1200,
    height: int = 900,
    max_acc: int = 100,
    stay_radius_m: float = 150.0,
    stay_minutes: float = 20.0,
    gap_minutes: float = 45.0,
    gap_metres: float = 250.0,
    dwell_max_kmh: float = 1.0,
    session: Session = Depends(get_session),
):
    from .owntracks_maps import render_for_day

    dt_obj = _owntracks_day(dt, tz, session)
    params = _track_params(
        max_acc, stay_radius_m, stay_minutes, gap_minutes, gap_metres, dwell_max_kmh
    )
    try:
        png, _, content_hash = render_for_day(
            dt_obj, session, params, width=width, height=height
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    etag = f'"{content_hash}-{width}x{height}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return Response(
        content=png,
        media_type="image/png",
        headers={"ETag": etag, "Cache-Control": "private, max-age=3600"},
    )


@app.post("/owntracks/sync", operation_id="owntracksSyncLocations")
def owntracks_sync_locations(
    days_back: int = 7, session: Session = Depends(get_session)
):
    from .owntracks_connector import MyDiaryOwnTracks

    num_added = MyDiaryOwnTracks().save_locations_to_database(
        session=session, days_back=days_back
    )
    return {"num_added": num_added}


@app.post("/owntracks/map/{dt}/to_note", operation_id="owntracksMapToNote")
def owntracks_map_to_note(
    dt: str,
    tz: str = "infer",
    force: bool = False,
    session: Session = Depends(get_session),
    mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client),
):
    """Render the day's map and write it into the note's Location section."""
    from .owntracks_maps import sync_day_map_to_note

    dt_obj = _owntracks_day(dt, tz, session)
    try:
        result = sync_day_map_to_note(
            dt_obj, session=session, mydiary_joplin=mydiary_joplin, force=force
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"result": result}


@app.post(
    "/images/upload/{note_id}",
    operation_id="uploadImagesToNote",
    response_model=List[MyDiaryImageRead],
)
async def upload_images_to_note(
    *,
    session: Session = Depends(get_session),
    note_id: str,
    dt: str,
    files: List[UploadFile] = File(...),
    mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client),
):
    """Store uploaded originals in Nextcloud (mydiary_uploads/{YYYY}/{MM}/), then
    run them through the same shrink/database/Joplin pipeline as iPhone photos."""
    from .image_sync import UPLOADS_BASEDIR, sync_note_images

    diary_date = pendulum.parse(dt).date()
    mydiary_nextcloud = MyDiaryNextcloud()
    target_dir = f"{UPLOADS_BASEDIR}/{diary_date.year}/{diary_date.month:02d}"
    mydiary_nextcloud.mkdirs(target_dir)

    upload_paths = []
    for f in files:
        filename = Path(f.filename or "").name
        if not filename:
            raise HTTPException(status_code=400, detail="upload has no filename")
        stem, ext = os.path.splitext(filename)
        candidate = filename
        suffix = 0
        while mydiary_nextcloud.file_exists(
            f"{target_dir}/{requests.utils.quote(candidate)}"
        ):
            suffix += 1
            candidate = f"{stem}-{suffix}{ext}"
        nextcloud_path = f"{target_dir}/{requests.utils.quote(candidate)}"
        mydiary_nextcloud.upload_file(nextcloud_path, await f.read())
        upload_paths.append(nextcloud_path)

    # add the new uploads to the note alongside whatever is already there
    note = mydiary_joplin.get_note(note_id)
    current_ids = note.md_note.get_image_resource_ids()
    current_paths = [
        img.nextcloud_path
        for resource_id in current_ids
        for img in [
            session.exec(
                select(MyDiaryImage).where(
                    MyDiaryImage.joplin_resource_id == resource_id
                )
            ).first()
        ]
        if img is not None and img.nextcloud_path
    ]
    sync_note_images(
        session=session,
        mydiary_joplin=mydiary_joplin,
        mydiary_nextcloud=mydiary_nextcloud,
        note_id=note_id,
        desired_paths=current_paths + upload_paths,
        diary_date=diary_date,
    )
    return [
        session.exec(
            select(MyDiaryImage).where(MyDiaryImage.nextcloud_path == path)
        ).one()
        for path in upload_paths
    ]


@app.get(
    "/images/uploads/{dt}",
    operation_id="uploadedImagesForDay",
    response_model=List[MyDiaryImageRead],
)
def uploaded_images_for_day(dt: str, session: Session = Depends(get_session)):
    diary_date = pendulum.parse(dt).date()
    return session.exec(
        select(MyDiaryImage)
        .where(MyDiaryImage.diary_date == diary_date)
        .order_by(MyDiaryImage.created_at)
    ).all()


@app.post(
    "/images/sync_note/{note_id}",
    operation_id="syncNoteImages",
    response_model=dict,
)
async def sync_note_images_route(
    *,
    session: Session = Depends(get_session),
    note_id: str,
    photos: List[str],
    dt: Optional[str] = None,
    mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client),
):
    """Two-way sync: make the note's images section match `photos` (the full
    desired list of nextcloud paths, in display order)."""
    from .image_sync import sync_note_images

    return sync_note_images(
        session=session,
        mydiary_joplin=mydiary_joplin,
        mydiary_nextcloud=MyDiaryNextcloud(),
        note_id=note_id,
        desired_paths=photos,
        diary_date=pendulum.parse(dt).date() if dt else None,
    )


@app.post(
    "/performsongs/", operation_id="createPerformSong", response_model=PerformSongRead
)
def create_perform_song(
    *, session: Session = Depends(get_session), perform_song: PerformSongCreate
):
    perform_song.spotify_id = normalize_spotify_id(perform_song.spotify_id)
    db_perform_song = PerformSong.model_validate(perform_song)
    session.add(db_perform_song)
    session.commit()
    session.refresh(db_perform_song)
    return db_perform_song


@app.get("/performsongs/count", operation_id="performSongCount", response_model=int)
async def perform_song__count(*, session: Session = Depends(get_session)):
    stmt = select(func.count(PerformSong.id))
    return session.exec(stmt).one()


@app.get(
    "/performsongs/",
    operation_id="readPerformSongsList",
    response_model=List[PerformSongRead],
)
def read_perform_songs(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=5000),
):
    perform_songs = session.exec(select(PerformSong).offset(offset).limit(limit)).all()
    return perform_songs


@app.get(
    "/performsongs/{perform_song_id}",
    operation_id="readPerformSong",
    response_model=PerformSongRead,
)
def read_perform_song(
    *,
    session: Session = Depends(get_session),
    perform_song_id: int,
):
    perform_song = session.get(PerformSong, perform_song_id)
    if not perform_song:
        raise HTTPException(status_code=404, detail="PerformSong not found")
    return perform_song


@app.patch(
    "/performsongs/{perform_song_id}",
    operation_id="updatePerformSong",
    response_model=PerformSongRead,
)
def update_perform_song(
    *,
    session: Session = Depends(get_session),
    perform_song_id: int,
    perform_song: PerformSongUpdate,
):
    db_perform_song = session.get(PerformSong, perform_song_id)
    if not db_perform_song:
        raise HTTPException(status_code=404, detail="PerformSong not found")
    perform_song_data = perform_song.model_dump(exclude_unset=True)
    if perform_song_data.get("spotify_id"):
        perform_song_data["spotify_id"] = normalize_spotify_id(
            perform_song_data["spotify_id"]
        )
    db_perform_song.sqlmodel_update(perform_song_data)
    session.add(db_perform_song)
    session.commit()
    session.refresh(db_perform_song)
    return db_perform_song


@app.delete("/performsongs/{perform_song_id}", operation_id="deletePerformSong")
def delete_perform_song(
    *, session: Session = Depends(get_session), perform_song_id: int
):
    db_perform_song = session.get(PerformSong, perform_song_id)
    if not db_perform_song:
        raise HTTPException(status_code=404, detail="PerformSong not found")
    session.delete(db_perform_song)
    session.commit()
    return {"ok": True}


@app.post("/dogs/", operation_id="createDog", response_model=DogRead)
def create_dog(*, session: Session = Depends(get_session), dog: DogCreate):
    db_dog = Dog.model_validate(dog)
    session.add(db_dog)
    session.commit()
    session.refresh(db_dog)
    return db_dog


@app.get("/dogs/", operation_id="readDogsList", response_model=List[DogRead])
def read_dogs(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=1000),
):
    dogs = session.exec(select(Dog).offset(offset).limit(limit)).all()
    return dogs


@app.get("/dogs/{dog_id}", operation_id="readDog", response_model=DogRead)
def read_dog(
    *,
    session: Session = Depends(get_session),
    dog_id: int,
):
    dog = session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    return dog


@app.patch("/dogs/{dog_id}", operation_id="updateDog", response_model=DogRead)
def update_dog(
    *,
    session: Session = Depends(get_session),
    dog_id: int,
    dog: DogUpdate,
):
    db_dog = session.get(Dog, dog_id)
    if not db_dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    dog_data = dog.model_dump(exclude_unset=True)
    for k, v in dog_data.items():
        setattr(db_dog, k, v)
    session.add(db_dog)
    session.commit()
    session.refresh(db_dog)
    return db_dog


@app.delete("/dogs/{dog_id}", operation_id="deleteDog")
def delete_dog(*, session: Session = Depends(get_session), dog_id: int):
    db_dog = session.get(Dog, dog_id)
    if not db_dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    session.delete(db_dog)
    session.commit()
    return {"ok": True}


@app.post("/recipes/", operation_id="createRecipe", response_model=RecipeRead)
def create_recipe(*, session: Session = Depends(get_session), recipe: RecipeCreate):
    db_recipe = Recipe.model_validate(recipe)
    session.add(db_recipe)
    session.commit()
    session.refresh(db_recipe)
    return db_recipe


@app.get("/recipes/", operation_id="readRecipesList", response_model=RecipeRead)
def read_recipes(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=1000),
):
    recipes = session.exec(select(Recipe).offset(offset).limit(limit)).all()
    return recipes


@app.get(
    "/tzchange/",
    operation_id="readTimeZoneChangeList",
    response_model=List[TimeZoneChange],
)
def read_timezonechange(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=1000),
):
    tz_changes = session.exec(select(TimeZoneChange).offset(offset).limit(limit)).all()
    return sorted(tz_changes, key=lambda x: x.changed_at)


@app.post(
    "/tzchange/", operation_id="createTimeZoneChange", response_model=TimeZoneChange
)
def create_timezonechange(
    *, session: Session = Depends(get_session), dt: str, tz_before: str, tz_after: str
):
    dt_str = dt.split("Z")[0]
    dt_resolved = pendulum.parse(dt_str, tz=tz_after)
    tz_change = TimeZoneChange.model_validate(
        {
            "changed_at": dt_resolved.in_timezone("UTC"),
            "tz_before": tz_before,
            "tz_after": tz_after,
        }
    )
    session.add(tz_change)
    session.commit()
    session.refresh(tz_change)
    return tz_change


def _miss_read(miss: SpellingBeeMiss) -> SpellingBeeMissRead:
    return SpellingBeeMissRead(
        **miss.model_dump(), is_pangram=spelling_bee.is_pangram(miss.word)
    )


def _date_consistency(
    session: Session,
    puzzle_date: date,
    existing: Set[str],
    incoming: List[str],
    payload: Optional[SpellingBeeMissBulkCreate] = None,
) -> spelling_bee.Consistency:
    """Check a date's whole word list, existing plus incoming, as one puzzle."""
    center = payload.center_letter if payload else None
    outer = payload.outer_letters if payload else None
    if not center or not outer:
        puzzle = session.get(SpellingBeePuzzle, puzzle_date)
        if puzzle:
            center, outer = puzzle.center_letter, puzzle.outer_letters
    return spelling_bee.check_consistency(
        sorted(existing) + [w for w in incoming if w not in existing],
        center_letter=center,
        outer_letters=outer,
    )


@app.post(
    "/spellingbee/misses/",
    operation_id="createSpellingBeeMisses",
    response_model=SpellingBeeMissBulkResult,
)
def create_spelling_bee_misses(
    *, session: Session = Depends(get_session), payload: SpellingBeeMissBulkCreate
):
    valid, invalid = spelling_bee.validate_words(payload.words)

    existing = set(
        session.exec(
            select(SpellingBeeMiss.word).where(
                SpellingBeeMiss.puzzle_date == payload.puzzle_date
            )
        ).all()
    )

    # a date is one puzzle. filing a second day's answers under it silently
    # breaks the hive and the letter counts, so refuse rather than warn.
    consistency = _date_consistency(
        session, payload.puzzle_date, existing, valid, payload
    )
    if not consistency.ok:
        raise HTTPException(
            status_code=409,
            detail=(
                "These words can't all be from the puzzle already recorded for "
                f"{payload.puzzle_date}. " + " ".join(consistency.problems)
            ),
        )
    now = pendulum.now().in_timezone("UTC")
    created = []
    skipped = []
    for word in valid:
        if word in existing:
            skipped.append(word)
            continue
        miss = SpellingBeeMiss(
            puzzle_date=payload.puzzle_date, word=word, created_at=now
        )
        session.add(miss)
        created.append(miss)

    # letters are optional, and only recorded when the caller bothered to
    if payload.center_letter and payload.outer_letters:
        _upsert_puzzle(
            session, payload.puzzle_date, payload.center_letter, payload.outer_letters
        )

    session.commit()
    for miss in created:
        session.refresh(miss)

    return SpellingBeeMissBulkResult(
        puzzle_date=payload.puzzle_date,
        created=[_miss_read(m) for m in created],
        skipped=skipped,
        invalid=invalid,
    )


@app.post(
    "/spellingbee/misses/check",
    operation_id="previewSpellingBeeMisses",
    response_model=SpellingBeeAddPreview,
)
def preview_spelling_bee_misses(
    *, session: Session = Depends(get_session), payload: SpellingBeeMissBulkCreate
):
    """Dry run of an add, so the form can warn before it writes anything."""
    valid, invalid = spelling_bee.validate_words(payload.words)
    existing = set(
        session.exec(
            select(SpellingBeeMiss.word).where(
                SpellingBeeMiss.puzzle_date == payload.puzzle_date
            )
        ).all()
    )
    new_words = [w for w in valid if w not in existing]
    duplicates = [w for w in valid if w in existing]

    consistency = _date_consistency(
        session, payload.puzzle_date, existing, valid, payload
    )
    combined = sorted(existing) + new_words

    return SpellingBeeAddPreview(
        puzzle_date=payload.puzzle_date,
        existing_words=sorted(existing),
        new_words=new_words,
        duplicate_words=duplicates,
        invalid_words=invalid,
        conflict=not consistency.ok,
        problems=list(consistency.problems),
        combined_letters=list(consistency.letters),
        center_candidates=list(consistency.center_candidates),
        groups=spelling_bee.split_by_puzzle(combined) if not consistency.ok else [],
    )


@app.get(
    "/spellingbee/misses/",
    operation_id="readSpellingBeeMissesList",
    response_model=List[SpellingBeeMissRead],
)
def read_spelling_bee_misses(
    *,
    session: Session = Depends(get_session),
    puzzle_date: Optional[date] = None,
    offset: int = 0,
    limit: int = Query(default=500, lte=5000),
):
    stmt = select(SpellingBeeMiss)
    if puzzle_date:
        stmt = stmt.where(SpellingBeeMiss.puzzle_date == puzzle_date)
    misses = session.exec(stmt.offset(offset).limit(limit)).all()
    return [_miss_read(m) for m in misses]


@app.get(
    "/spellingbee/words/",
    operation_id="readSpellingBeeWordsList",
    response_model=List[SpellingBeeWordRead],
)
def read_spelling_bee_words(
    *,
    session: Session = Depends(get_session),
    min_misses: int = Query(default=1, ge=1),
    offset: int = 0,
    limit: int = Query(default=1000, lte=5000),
):
    """Every distinct word, rolled up across the days it was missed.

    Aggregated in Python rather than SQL: the volume is a handful of words a
    day, and the per-word list of dates would need group_concat and
    string-splitting to come back out of a GROUP BY.
    """
    misses = session.exec(select(SpellingBeeMiss)).all()
    definitions = {
        d.word: d for d in session.exec(select(SpellingBeeDefinition)).all()
    }

    by_word: Dict[str, List[SpellingBeeMiss]] = {}
    for miss in misses:
        by_word.setdefault(miss.word, []).append(miss)

    words = []
    for word, word_misses in by_word.items():
        if len(word_misses) < min_misses:
            continue
        word_misses = sorted(word_misses, key=lambda m: m.puzzle_date)
        definition = definitions.get(word)
        words.append(
            SpellingBeeWordRead(
                word=word,
                times_missed=len(word_misses),
                first_missed=word_misses[0].puzzle_date,
                last_missed=word_misses[-1].puzzle_date,
                misses=[
                    SpellingBeeWordMiss(id=m.id, puzzle_date=m.puzzle_date)
                    for m in word_misses
                ],
                is_pangram=spelling_bee.is_pangram(word),
                definition=definition.definition if definition else None,
                part_of_speech=definition.part_of_speech if definition else None,
            )
        )

    # most-missed first -- those are the ones worth practising
    words.sort(key=lambda w: (-w.times_missed, w.word))
    return words[offset : offset + limit]


@app.get(
    "/spellingbee/hives/",
    operation_id="readSpellingBeeHivesList",
    response_model=List[SpellingBeeHiveRead],
)
def read_spelling_bee_hives(
    *,
    session: Session = Depends(get_session),
    min_words: int = Query(default=3, ge=1),
    limit: int = Query(default=500, lte=5000),
):
    """One playable board per recorded day, newest first."""
    misses = session.exec(select(SpellingBeeMiss)).all()
    puzzles = {p.puzzle_date: p for p in session.exec(select(SpellingBeePuzzle)).all()}

    by_date: Dict[date, List[str]] = {}
    for miss in misses:
        by_date.setdefault(miss.puzzle_date, []).append(miss.word)

    hives = []
    for puzzle_date, words in by_date.items():
        if len(words) < min_words:
            continue
        puzzle = puzzles.get(puzzle_date)
        hive = spelling_bee.derive_hive(
            puzzle_date,
            words,
            center_letter=puzzle.center_letter if puzzle else None,
            outer_letters=puzzle.outer_letters if puzzle else None,
        )
        if not hive.words:
            continue
        hives.append(
            SpellingBeeHiveRead(
                puzzle_date=hive.puzzle_date,
                center_letter=hive.center_letter,
                outer_letters=list(hive.outer_letters),
                exact=hive.exact,
                words=list(hive.words),
                pangrams=list(hive.pangrams),
                warnings=list(hive.warnings),
            )
        )

    hives.sort(key=lambda h: h.puzzle_date, reverse=True)
    return hives[:limit]


@app.get(
    "/spellingbee/puzzles/",
    operation_id="readSpellingBeePuzzlesList",
    response_model=List[SpellingBeePuzzleRead],
)
def read_spelling_bee_puzzles(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=500, lte=5000),
):
    puzzles = session.exec(select(SpellingBeePuzzle).offset(offset).limit(limit)).all()
    return sorted(puzzles, key=lambda p: p.puzzle_date, reverse=True)


@app.patch(
    "/spellingbee/misses/{miss_id}",
    operation_id="updateSpellingBeeMiss",
    response_model=SpellingBeeMissRead,
)
def update_spelling_bee_miss(
    *,
    session: Session = Depends(get_session),
    miss_id: int,
    miss: SpellingBeeMissUpdate,
):
    db_miss = session.get(SpellingBeeMiss, miss_id)
    if not db_miss:
        raise HTTPException(status_code=404, detail="SpellingBeeMiss not found")
    miss_data = miss.model_dump(exclude_unset=True)
    if miss_data.get("word"):
        miss_data["word"] = spelling_bee.normalize_word(miss_data["word"])
    db_miss.sqlmodel_update(miss_data)
    session.add(db_miss)
    session.commit()
    session.refresh(db_miss)
    return _miss_read(db_miss)


@app.delete("/spellingbee/misses/{miss_id}", operation_id="deleteSpellingBeeMiss")
def delete_spelling_bee_miss(
    *, session: Session = Depends(get_session), miss_id: int
):
    db_miss = session.get(SpellingBeeMiss, miss_id)
    if not db_miss:
        raise HTTPException(status_code=404, detail="SpellingBeeMiss not found")
    session.delete(db_miss)
    session.commit()
    return {"ok": True}


def _upsert_puzzle(
    session: Session, puzzle_date: date, center_letter: str, outer_letters: str
) -> SpellingBeePuzzle:
    center = spelling_bee.normalize_word(center_letter)
    outer = spelling_bee.normalize_word(outer_letters)
    # note that S is perfectly legal here. it's rare in real puzzles, which is
    # why it's never *guessed* when deriving a hive, but a recorded S puzzle
    # must be storable.
    if len(center) != 1 or len(outer) != spelling_bee.HIVE_SIZE - 1:
        raise HTTPException(
            status_code=422,
            detail="A puzzle needs one center letter and six outer letters",
        )
    if len({center} | set(outer)) != spelling_bee.HIVE_SIZE:
        raise HTTPException(
            status_code=422, detail="The seven letters must all be different"
        )

    db_puzzle = session.get(SpellingBeePuzzle, puzzle_date)
    if db_puzzle:
        db_puzzle.center_letter = center
        db_puzzle.outer_letters = outer
    else:
        db_puzzle = SpellingBeePuzzle(
            puzzle_date=puzzle_date,
            center_letter=center,
            outer_letters=outer,
            created_at=pendulum.now().in_timezone("UTC"),
        )
    session.add(db_puzzle)
    return db_puzzle


@app.put(
    "/spellingbee/puzzles/{puzzle_date}",
    operation_id="upsertSpellingBeePuzzle",
    response_model=SpellingBeePuzzleRead,
)
def upsert_spelling_bee_puzzle(
    *,
    session: Session = Depends(get_session),
    puzzle_date: date,
    puzzle: SpellingBeePuzzleUpsert,
):
    db_puzzle = _upsert_puzzle(
        session, puzzle_date, puzzle.center_letter, puzzle.outer_letters
    )
    session.commit()
    session.refresh(db_puzzle)
    return db_puzzle


@app.post(
    "/spellingbee/definitions/{word}",
    operation_id="fetchSpellingBeeDefinition",
    response_model=SpellingBeeDefinitionRead,
)
def fetch_spelling_bee_definition(
    *,
    session: Session = Depends(get_session),
    word: str,
    refresh: bool = False,
):
    """Look a word up, caching the answer -- including "not found"."""
    word = spelling_bee.normalize_word(word)
    if not word:
        raise HTTPException(status_code=422, detail="No word given")

    db_definition = session.get(SpellingBeeDefinition, word)
    if db_definition and not refresh:
        return db_definition

    definition, part_of_speech = fetch_definition(word)
    if db_definition:
        db_definition.definition = definition
        db_definition.part_of_speech = part_of_speech
        db_definition.fetched_at = pendulum.now().in_timezone("UTC")
    else:
        db_definition = SpellingBeeDefinition(
            word=word,
            definition=definition,
            part_of_speech=part_of_speech,
            fetched_at=pendulum.now().in_timezone("UTC"),
        )
    session.add(db_definition)
    session.commit()
    session.refresh(db_definition)
    return db_definition


@app.get("/generate_openapi_json")
def send_api_json():
    return app.openapi()


### Experimental


@app.get("/experimental/get_spotify_playlist")
def experimental_get_spotify_playlist(playlist_id: str):
    from mydiary.spotify_connector import MyDiarySpotify, normalize_spotify_id

    mydiary_spotify = MyDiarySpotify()
    playlist_id = normalize_spotify_id(playlist_id)
    playlist = mydiary_spotify.sp.playlist(playlist_id)
    tracks = playlist["tracks"]
    tracks_items = tracks["items"]
    while tracks["next"]:
        tracks = mydiary_spotify.sp.next(tracks)
        tracks_items = tracks["items"]
        playlist["tracks"]["items"] += tracks_items
    return playlist


@app.get("/experimental/get_spotify_audio_features")
def experimental_get_spotify_audio_features(track_id: str):
    from mydiary.spotify_connector import MyDiarySpotify, normalize_spotify_id

    mydiary_spotify = MyDiarySpotify()
    track_id = normalize_spotify_id(track_id)
    return mydiary_spotify.sp.audio_features(track_id)


@app.get("/experimental/lifespan")
def experimental_lifespan():
    # f = io.StringIO()
    # scheduler.export_jobs(f)
    # f.seek(0)
    # txt = f.read()
    # logger.info(txt)
    # return json.loads(txt)
    print(pendulum.now())
    scheduler.print_jobs()


@app.get("/experimental/joplinevents")
def joplinevents(mydiary_joplin: MyDiaryJoplin = Depends(get_joplin_client)):

    # params = {
    #     "token": mydiary_joplin.token,
    #     "cursor": pendulum.now().subtract(days=100).int_timestamp,
    # }
    # r = requests.get(f"{mydiary_joplin.base_url}/events", params=params)
    # return r.json()
    fields = [
        "id",
        "parent_id",
        "title",
        "body",
        "created_time",
        "updated_time",
        "source",
    ]
    params = {
        "token": mydiary_joplin.token,
        "fields": fields,
        "query": "updated:20241220",
        "limit": 25,
        "order_by": "updated_time",
        "order_dir": "DESC",
    }
    # r = requests.get(f"{mydiary_joplin.base_url}/notes", params=params)
    r = requests.get(f"{mydiary_joplin.base_url}/search", params=params)
    return r.json()
    # items = r.json()["items"]
    # dt = pendulum.now().subtract(days=10)
    # return {
    #     # "items": [item for item in items if int(item["updated_time"])//1000>dt.int_timestamp],
    #     "items": items,
    #     "dt": dt.int_timestamp,
    #     "has_more": r.json().get("has_more", False)
    # }


if __name__ == "__main__":
    uvicorn.run(
        "mydiary.api:app",
        proxy_headers=True,
        host="0.0.0.0",
        reload=True,
        port=8888,
        timeout_keep_alive=120,
        log_level="debug",
        access_log=True,
    )
