from datetime import datetime
import requests
import io
import pendulum
from typing import List, Optional, Set, Tuple
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import pydantic
from sqlalchemy import desc, all_
from sqlalchemy.sql.functions import count
from sqlmodel import Field, SQLModel
from fastapi import Query
from .db import Session, engine, select
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
    Tag,
    PocketArticle,
    GooglePhotosThumbnail,
)
from .googlephotos_connector import MyDiaryGooglePhotos
import uvicorn

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


class GoogleCalendarEventRead(GoogleCalendarEvent):
    pass


class TagRead(Tag):
    id_: int = Field(alias="id")
    num_pocket_articles: Optional[int] = None


class PocketArticleRead(PocketArticle):
    tags_: List[TagRead] = Field(alias="tags")


class SpotifyTrackHistoryCreate(SpotifyTrackHistoryBase):
    pass


class SpotifyTrackHistoryRead(SpotifyTrackHistoryBase):
    # id: int
    id_: int = Field(alias="id")
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
    key: Optional[str]
    capo: Optional[int]


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


def get_session():
    with Session(engine) as session:
        yield session


# app = FastAPI()
app = FastAPI(title="mydiary", root_path="/api", openapi_url="/api/openapi.json")
# app = FastAPI(title="mydiary", openapi_url="/api")
# app = FastAPI(title="mydiary", root_path="/api")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

# @app.get("/api/app")
# def read_main(request: Request):
#     return {"message": "Hello World", "root_path": request.scope.get("root_path")}


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
        item = TagRead.from_orm(tag)
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
        # stmt = stmt.where(PocketArticle.status==status)
        stmt = stmt.where(PocketArticle.status.in_(status))
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


@app.post("/joplin/sync", operation_id="joplinSync")
async def joplin_sync():
    from mydiary.joplin_connector import MyDiaryJoplin

    with MyDiaryJoplin(init_config=False) as mydiary_joplin:
        logger.info("starting Joplin sync")
        try:
            mydiary_joplin.sync()
        except RuntimeError:
            raise HTTPException(status_code=500)
        logger.info("sync complete")
    return "sync complete"


@app.get("/joplin/get_note_id/{dt}", operation_id="joplinGetNoteId", response_model=str)
def joplin_get_note_id(dt: str) -> str:
    from mydiary import MyDiaryDay
    from mydiary.joplin_connector import MyDiaryJoplin

    if dt == "today":
        dt = pendulum.today()
    elif dt == "yesterday":
        dt = pendulum.yesterday()
    else:
        dt = pendulum.parse(dt)
    with MyDiaryJoplin(init_config=False) as mydiary_joplin:
        day = MyDiaryDay.from_dt(dt, joplin_connector=mydiary_joplin)

        existing_id = day.get_joplin_note_id()
        # if existing_id == "does_not_exist":
        #     raise RuntimeError(
        #         f"Joplin note does not already exist for date {dt.to_date_string()}!"
        #     )
        return existing_id


@app.post("/joplin/init_note/{dt}", operation_id="joplinInitNote")
def joplin_init_note(dt: str, tz: str = "local"):
    from mydiary import MyDiaryDay
    from mydiary.joplin_connector import MyDiaryJoplin

    if dt == "today":
        dt = pendulum.today(tz=tz)
    elif dt == "yesterday":
        dt = pendulum.yesterday(tz=tz)
    else:
        dt = pendulum.parse(dt, tz=tz)
    with MyDiaryJoplin(init_config=False) as mydiary_joplin:
        day = MyDiaryDay.from_dt(dt, joplin_connector=mydiary_joplin)
        day.init_joplin_note(joplin_connector=mydiary_joplin, post_sync=True)


@app.get(
    "/googlephotos/thumbnails/{dt}",
    operation_id="googlePhotosThumbnailUrls",
    response_model=List[GooglePhotosThumbnail],
)
def google_photos_thumbnails_url(dt: str):
    if dt == "today":
        dt = pendulum.today()
    elif dt == "yesterday":
        dt = pendulum.yesterday()
    else:
        dt = pendulum.parse(dt)

    mydiary_googlephotos = MyDiaryGooglePhotos()
    items = mydiary_googlephotos.query_photos_api_for_day(dt)
    items = [
        {
            # "url": mydiary_googlephotos.get_thumbnail_download_url(item),
            "baseUrl": item["baseUrl"],
            "width": item["mediaMetadata"]["width"],
            "height": item["mediaMetadata"]["height"],
            "creationTime": pendulum.parse(item["mediaMetadata"]["creationTime"]),
        }
        for item in items
    ]
    items.sort(key=lambda item: item["creationTime"])
    return items


@app.post(
    "/googlephotos/add_to_joplin/{note_id}",
    operation_id="googlePhotosAddToJoplin",
)
async def google_photos_add_to_joplin(
    note_id: str, photos: List[GooglePhotosThumbnail]
):
    from mydiary import MyDiaryDay
    from mydiary.joplin_connector import MyDiaryJoplin
    from mydiary.markdown_edits import MarkdownDoc
    from mydiary.core import reduce_size_recurse

    with MyDiaryJoplin(init_config=False) as mydiary_joplin:
        note = mydiary_joplin.get_note(note_id)
        md_note = MarkdownDoc(note.body, parent=note)

        sec_images = md_note.get_section_by_title("images")
        resource_ids = sec_images.get_resource_ids()
        if resource_ids:
            raise RuntimeError()
        size = (512, 512)
        bytes_threshold = 60000
        resource_ids = []
        for photo in photos:
            download_url = f"{photo.baseUrl}=d"
            image_bytes_request = requests.get(download_url)
            image_bytes: bytes = image_bytes_request.content
            if len(image_bytes) > bytes_threshold:
                image_bytes = reduce_size_recurse(image_bytes, size, bytes_threshold)
            r = mydiary_joplin.create_resource(data=image_bytes)
            r.raise_for_status()
            resource_id = r.json()["id"]
            resource_ids.append(f"![](:/{resource_id})")
            logger.debug(f"new resource id: {resource_id}")

        new_txt = sec_images.txt
        new_txt += "\n"
        new_txt += "\n\n".join(resource_ids)
        new_txt += "\n"
        sec_images.update(new_txt)
        logger.info(f"updating note: {note.title}")
        r_put_note = mydiary_joplin.update_note_body(note.id, md_note.txt)
        r_put_note.raise_for_status()

        await joplin_sync()


@app.post(
    "/performsongs/", operation_id="createPerformSong", response_model=PerformSongRead
)
def create_perform_song(
    *, session: Session = Depends(get_session), perform_song: PerformSongCreate
):
    db_perform_song = PerformSong.from_orm(perform_song)
    session.add(db_perform_song)
    session.commit()
    session.refresh(db_perform_song)
    return db_perform_song


@app.get(
    "/performsongs/",
    operation_id="readPerformSongsList",
    response_model=List[PerformSongRead],
)
def read_perform_songs(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=1000),
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
    perform_song_data = perform_song.dict(exclude_unset=True)
    for k, v in perform_song_data.items():
        setattr(db_perform_song, k, v)
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
    db_dog = Dog.from_orm(dog)
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
    dog_data = dog.dict(exclude_unset=True)
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
    db_recipe = Recipe.from_orm(recipe)
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


@app.get("/generate_openapi_json")
def send_api_json():
    return app.openapi()


if __name__ == "__main__":
    uvicorn.run(
        "mydiary.api:app",
        proxy_headers=True,
        host="0.0.0.0",
        reload=True,
        port=8888,
        timeout_keep_alive=30,
    )
