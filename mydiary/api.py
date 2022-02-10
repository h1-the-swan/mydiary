from typing import List
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, SQLModel
from .db import Session, engine, select
from .models import GoogleCalendarEvent, Tag, PocketArticle


class GoogleCalendarEventRead(GoogleCalendarEvent):
    pass


class TagRead(Tag):
    id_: int = Field(alias="id")


class PocketArticleRead(PocketArticle):
    tags_: List[TagRead] = Field(alias="tags")


def get_session():
    with Session(engine) as session:
        yield session


app = FastAPI()


@app.get("/gcal/events", response_model=List[GoogleCalendarEventRead])
def read_gcal_events(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=100)
):
    events = session.exec(select(GoogleCalendarEvent).offset(offset).limit(limit)).all()
    return events


@app.get("/tags", response_model=List[TagRead])
def read_tags(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=100)
):
    tags = session.exec(select(Tag).offset(offset).limit(limit)).all()
    return tags


@app.get("/pocket/articles", response_model=List[PocketArticleRead])
def read_pocket_articles(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, lte=100)
):
    articles = session.exec(select(PocketArticle).offset(offset).limit(limit)).all()
    return articles
