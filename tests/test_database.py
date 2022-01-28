import json
from pathlib import Path
import pendulum
import pytest
# from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from mydiary.spotify_history import SpotifyTrackHistory, SpotifyTrackHistoryCreate


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_add_spotify_track_history_to_database(rootdir: str, session: Session):
    fp = Path(rootdir).joinpath("spotifytrack.json")
    track_json = json.loads(fp.read_text())
    spotify_track = SpotifyTrackHistoryCreate.from_spotify_track(track_json)
    db_track = SpotifyTrackHistory.from_orm(spotify_track)
    session.add(db_track)
    session.commit()
    session.refresh(db_track)

    assert track_json["track"]["id"] == db_track.spotify_id
    assert track_json["track"]["name"] == db_track.name
    assert pendulum.parser.parse(track_json["played_at"]) == pendulum.instance(db_track.played_at)
