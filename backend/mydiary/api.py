from datetime import datetime
import pendulum
from typing import List, Optional, Set
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import pydantic
from sqlalchemy import desc, all_
from sqlmodel import Field, SQLModel
from fastapi import Query
from .db import Session, engine, select
from .models import (
    GoogleCalendarEvent,
    PocketStatusEnum,
    Tag,
    PocketArticle,
    GooglePhotosThumbnail,
)
from .googlephotos_connector import MyDiaryGooglePhotos
import uvicorn


class GoogleCalendarEventRead(GoogleCalendarEvent):
    pass


class TagRead(Tag):
    id_: int = Field(alias="id")


class PocketArticleRead(PocketArticle):
    tags_: List[TagRead] = Field(alias="tags")


def get_session():
    with Session(engine) as session:
        yield session


# app = FastAPI()
app = FastAPI(title="mydiary", root_path="/api", openapi_url="/api")

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
    limit: int = Query(default=100, lte=100),
):
    tags = session.exec(select(Tag).offset(offset).limit(limit)).all()
    return tags


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
    tags: Optional[Set[str]] = Query(None, description="Tag names"),  # tag names
    year: Optional[int] = Query(None, description="Year added"),
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
        for t in tags:
            stmt = stmt.where(PocketArticle.tags.any(Tag.name == t))

    if year is not None:
        # stmt = stmt.where(PocketArticle.time_added.year==year)
        # The above doesn't work (maybe a SQLite issue?) so do this instead:
        dt = pendulum.datetime(year=year, month=1, day=1)
        stmt = stmt.where(PocketArticle.time_added >= dt.start_of("year"))
        stmt = stmt.where(PocketArticle.time_added < dt.end_of("year"))
    articles = session.exec(stmt.offset(offset).limit(limit)).all()
    return articles


@app.get(
    "/googlephotos/thumbnails/{dt}",
    operation_id="googlePhotosThumbnailUrls",
    response_model=List[GooglePhotosThumbnail],
)
def google_photos_thumbnails_url(dt: str):
    dt = pendulum.parse(dt)
    mydiary_googlephotos = MyDiaryGooglePhotos()
    items = mydiary_googlephotos.query_photos_api_for_day(dt)
    return [
        {
            "url": mydiary_googlephotos.get_thumbnail_download_url(item),
            "width": item["mediaMetadata"]["width"],
            "height": item["mediaMetadata"]["height"],
        }
        for item in items
    ]


@app.get("/generate_openapi_json")
def send_api_json():
    return app.openapi()


if __name__ == "__main__":
    uvicorn.run(
        "mydiary.api:app", proxy_headers=True, host="0.0.0.0", reload=True, port=8888
    )
