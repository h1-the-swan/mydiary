# -*- coding: utf-8 -*-

import pendulum
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from mydiary.models import (
    PerformSong,
    PracticeRun,
    PracticeRunSection,
    SectionLevelOverride,
    SongArrangement,
)

NOW = pendulum.datetime(2026, 9, 19, 12, tz="UTC")


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def song(session: Session) -> PerformSong:
    s = PerformSong(name="Paper Lanterns", artist_name="The Invented Band", learned=False, key="Ab", capo=8)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


class TestTables:
    def test_arrangement_unique_per_instrument(self, session: Session, song: PerformSong):
        for _ in range(2):
            session.add(
                SongArrangement(
                    perform_song_id=song.id,
                    instrument="guitar",
                    sheet="",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        with pytest.raises(IntegrityError):
            session.commit()

    def test_run_sections_and_override_round_trip(self, session: Session, song: PerformSong):
        run = PracticeRun(perform_song_id=song.id, practiced_at=NOW)
        session.add(run)
        session.flush()
        session.add(PracticeRunSection(run_id=run.id, section_key="Chorus", stumbled=True, position=0))
        session.add(SectionLevelOverride(perform_song_id=song.id, section_key="Chorus", level="cues", set_at=NOW))
        session.commit()
        assert session.get(PracticeRunSection, (run.id, "Chorus")).stumbled is True
        assert session.get(SectionLevelOverride, (song.id, "Chorus")).level == "cues"
