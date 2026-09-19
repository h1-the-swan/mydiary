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


from datetime import timedelta

from mydiary import songs


def make_run(session, song, sections, when=NOW, arrangement=None):
    return songs.create_run(
        session, song.id, sections, arrangement=arrangement, practiced_at=when
    )


class TestArrangements:
    def test_first_guitar_arrangement_inherits_key_and_capo(self, session, song):
        arr = songs.create_arrangement(session, song, "guitar", sheet="[Chorus]\nla")
        assert (arr.key, arr.capo) == ("Ab", 8)
        assert arr.created_at is not None and arr.updated_at is not None

    def test_ukulele_does_not_inherit(self, session, song):
        arr = songs.create_arrangement(session, song, "ukulele")
        assert (arr.key, arr.capo) == (None, None)

    def test_explicit_key_wins(self, session, song):
        arr = songs.create_arrangement(session, song, "guitar", key="G", capo=0)
        assert (arr.key, arr.capo) == ("G", 0)

    def test_duplicate_instrument_raises(self, session, song):
        songs.create_arrangement(session, song, "guitar")
        with pytest.raises(songs.ArrangementExists):
            songs.create_arrangement(session, song, "guitar")

    def test_unknown_instrument_raises(self, session, song):
        with pytest.raises(ValueError):
            songs.create_arrangement(session, song, "banjo")

    def test_update_bumps_updated_at(self, session, song):
        arr = songs.create_arrangement(session, song, "guitar")
        before = arr.updated_at
        arr = songs.update_arrangement(session, arr, {"sheet": "[Verse 1]\nhello"})
        assert arr.sheet == "[Verse 1]\nhello"
        assert arr.updated_at >= before

    def test_delete_keeps_runs_but_detaches_them(self, session, song):
        arr = songs.create_arrangement(session, song, "guitar")
        run = make_run(session, song, [("Chorus", False)], arrangement=arr)
        songs.delete_arrangement(session, arr)
        session.refresh(run)
        assert run.arrangement_id is None
        assert run.instrument == "guitar"
        assert songs.arrangements_for_song(session, song.id) == []


class TestRuns:
    def test_run_copies_instrument_and_keeps_section_order(self, session, song):
        arr = songs.create_arrangement(session, song, "ukulele")
        run = make_run(session, song, [("Verse 1", False), ("Chorus", True)], arrangement=arr)
        assert run.instrument == "ukulele"
        secs = songs.sections_for_runs(session, [run.id])[run.id]
        assert [(s.section_key, s.stumbled, s.position) for s in secs] == [
            ("Verse 1", False, 0),
            ("Chorus", True, 1),
        ]

    def test_run_needs_a_section(self, session, song):
        with pytest.raises(ValueError):
            make_run(session, song, [])

    def test_run_rejects_duplicate_sections(self, session, song):
        with pytest.raises(ValueError):
            make_run(session, song, [("Chorus", False), ("Chorus", True)])

    def test_runs_for_song_newest_first(self, session, song):
        a = make_run(session, song, [("Chorus", False)], when=NOW)
        b = make_run(session, song, [("Chorus", False)], when=NOW + timedelta(hours=1))
        assert [r.id for r in songs.runs_for_song(session, song.id)] == [b.id, a.id]
        assert songs.last_practiced(session, song.id) == b.practiced_at.replace(tzinfo=None)


class TestLevels:
    def test_levels_from_runs(self, session, song):
        for i in range(3):
            make_run(session, song, [("Chorus", False), ("Verse 1", i == 2)], when=NOW + timedelta(days=i))
        levels = songs.levels_for_song(session, song.id)
        assert levels["Chorus"].level == "letters"
        assert levels["Verse 1"].level == "full"

    def test_override_and_clear(self, session, song):
        songs.set_override(session, song.id, "Bridge", "cues")
        assert songs.levels_for_song(session, song.id)["Bridge"].level == "cues"
        assert songs.clear_override(session, song.id, "Bridge") is True
        assert "Bridge" not in songs.levels_for_song(session, song.id)
        assert songs.clear_override(session, song.id, "Bridge") is False

    def test_override_rejects_unknown_level(self, session, song):
        with pytest.raises(ValueError):
            songs.set_override(session, song.id, "Bridge", "mostly")


class TestRename:
    def test_moves_history(self, session, song):
        make_run(session, song, [("Chorus?", True)])
        songs.set_override(session, song.id, "Chorus?", "letters")
        assert songs.rename_section(session, song.id, "Chorus?", "Chorus") == 1
        levels = songs.levels_for_song(session, song.id)
        assert "Chorus?" not in levels
        assert levels["Chorus"].num_runs == 1
        assert levels["Chorus"].overridden is True

    def test_merges_when_run_has_both_keys(self, session, song):
        run = make_run(session, song, [("A", True), ("B", False)])
        songs.rename_section(session, song.id, "A", "B")
        secs = songs.sections_for_runs(session, [run.id])[run.id]
        assert [(s.section_key, s.stumbled) for s in secs] == [("B", True)]

    def test_same_key_is_a_no_op(self, session, song):
        make_run(session, song, [("A", False)])
        assert songs.rename_section(session, song.id, "A", "A") == 0


class TestRunsForDay:
    def test_uses_the_days_timezone(self, session, song):
        # 23:30 in New York is 03:30 UTC the next day, and belongs to the NY day
        late = pendulum.datetime(2026, 9, 18, 23, 30, tz="America/New_York")
        make_run(session, song, [("Chorus", True), ("Bridge", False)], when=late.in_timezone("UTC"))
        day = pendulum.datetime(2026, 9, 18, tz="America/New_York")
        runs = songs.runs_for_day(session, day)
        assert len(runs) == 1
        assert runs[0].song_name == "Paper Lanterns"
        assert runs[0].stumbled == ["Chorus"]
        assert songs.runs_for_day(session, day.add(days=1)) == []
