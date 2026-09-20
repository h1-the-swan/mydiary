# -*- coding: utf-8 -*-

DESCRIPTION = """Database reads and writes for song arrangements and practice runs.

The level rules are pure and live in song_practice.py; this module only
gathers their inputs. Sheets are opaque ChordPro text here -- the frontend owns
parsing them, and practice runs arrive already keyed by section label."""

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import pendulum
from sqlalchemy import desc, func
from sqlmodel import Session, select

from .models import (
    PerformSong,
    PracticeRun,
    PracticeRunSection,
    SectionLevelOverride,
    SongArrangement,
)
from .song_practice import (
    LevelOverride,
    RunSummary,
    SectionLevel,
    SectionResult,
    section_level,
    validate_level,
)

INSTRUMENTS = ("guitar", "ukulele")


class ArrangementExists(Exception):
    """A song already has an arrangement for that instrument."""


def _utcnow() -> datetime:
    return pendulum.now("UTC")


def arrangements_for_song(session: Session, song_id: int) -> List[SongArrangement]:
    return list(
        session.exec(
            select(SongArrangement)
            .where(SongArrangement.perform_song_id == song_id)
            .order_by(SongArrangement.instrument)
        )
    )


def create_arrangement(
    session: Session,
    song: PerformSong,
    instrument: str,
    key: Optional[str] = None,
    capo: Optional[int] = None,
    sheet: str = "",
    source: str = "manual",
) -> SongArrangement:
    if instrument not in INSTRUMENTS:
        raise ValueError(f"unknown instrument {instrument!r}; expected one of {INSTRUMENTS}")
    existing = session.exec(
        select(SongArrangement)
        .where(SongArrangement.perform_song_id == song.id)
        .where(SongArrangement.instrument == instrument)
    ).first()
    if existing is not None:
        raise ArrangementExists(f"{song.name} already has a {instrument} arrangement")
    # PerformSong.key/capo have always described what is played on guitar
    if instrument == "guitar":
        key = song.key if key is None else key
        capo = song.capo if capo is None else capo
    now = _utcnow()
    arrangement = SongArrangement(
        perform_song_id=song.id,
        instrument=instrument,
        key=key,
        capo=capo,
        sheet=sheet,
        source=source,
        created_at=now,
        updated_at=now,
    )
    session.add(arrangement)
    session.commit()
    session.refresh(arrangement)
    return arrangement


def update_arrangement(
    session: Session, arrangement: SongArrangement, changes: dict
) -> SongArrangement:
    arrangement.sqlmodel_update(changes)
    arrangement.updated_at = _utcnow()
    session.add(arrangement)
    session.commit()
    session.refresh(arrangement)
    return arrangement


def delete_song_practice_data(session: Session, song_id: int) -> None:
    """Delete everything practice-related for a song, ahead of deleting the
    song itself. SQLite foreign keys aren't enforced here (see api.py's
    delete_perform_song), so this has to be done by hand, parent-first:
    a run's sections, then the run, then the song's arrangements and
    overrides."""
    run_ids = session.exec(
        select(PracticeRun.id).where(PracticeRun.perform_song_id == song_id)
    ).all()
    if run_ids:
        for section in session.exec(
            select(PracticeRunSection).where(PracticeRunSection.run_id.in_(run_ids))
        ):
            session.delete(section)
        for run in session.exec(
            select(PracticeRun).where(PracticeRun.id.in_(run_ids))
        ):
            session.delete(run)
    for arrangement in session.exec(
        select(SongArrangement).where(SongArrangement.perform_song_id == song_id)
    ):
        session.delete(arrangement)
    for override in session.exec(
        select(SectionLevelOverride).where(SectionLevelOverride.perform_song_id == song_id)
    ):
        session.delete(override)
    session.commit()


def delete_arrangement(session: Session, arrangement: SongArrangement) -> None:
    # runs belong to the song, not the sheet: keep them, minus the pointer
    for run in session.exec(
        select(PracticeRun).where(PracticeRun.arrangement_id == arrangement.id)
    ):
        run.arrangement_id = None
        session.add(run)
    session.delete(arrangement)
    session.commit()


def create_run(
    session: Session,
    song_id: int,
    sections: List[Tuple[str, bool]],
    arrangement: Optional[SongArrangement] = None,
    practiced_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> PracticeRun:
    """Record one run. `sections` is (section_key, stumbled) in sheet order,
    for the sections actually played."""
    if not sections:
        raise ValueError("a run needs at least one section")
    keys = [k for k, _ in sections]
    if len(set(keys)) != len(keys):
        raise ValueError("a section can only appear once in a run")
    run = PracticeRun(
        perform_song_id=song_id,
        arrangement_id=arrangement.id if arrangement else None,
        instrument=arrangement.instrument if arrangement else None,
        practiced_at=practiced_at or _utcnow(),
        note=note,
    )
    session.add(run)
    session.flush()
    for position, (key, stumbled) in enumerate(sections):
        session.add(
            PracticeRunSection(
                run_id=run.id, section_key=key, stumbled=stumbled, position=position
            )
        )
    session.commit()
    session.refresh(run)
    return run


def sections_for_runs(
    session: Session, run_ids: Iterable[int]
) -> Dict[int, List[PracticeRunSection]]:
    run_ids = list(run_ids)
    out: Dict[int, List[PracticeRunSection]] = {i: [] for i in run_ids}
    if not run_ids:
        return out
    for sec in session.exec(
        select(PracticeRunSection)
        .where(PracticeRunSection.run_id.in_(run_ids))
        .order_by(PracticeRunSection.run_id, PracticeRunSection.position)
    ):
        out[sec.run_id].append(sec)
    return out


def runs_for_song(session: Session, song_id: int) -> List[PracticeRun]:
    return list(
        session.exec(
            select(PracticeRun)
            .where(PracticeRun.perform_song_id == song_id)
            .order_by(desc(PracticeRun.practiced_at))
        )
    )


def last_practiced(session: Session, song_id: int) -> Optional[datetime]:
    return session.exec(
        select(func.max(PracticeRun.practiced_at)).where(
            PracticeRun.perform_song_id == song_id
        )
    ).one()


def levels_for_song(session: Session, song_id: int) -> Dict[str, SectionLevel]:
    """Levels for every section with runs or an override. A section with
    neither is at `full`, and the frontend assumes so without asking."""
    rows = session.exec(
        select(
            PracticeRunSection.section_key,
            PracticeRun.practiced_at,
            PracticeRunSection.stumbled,
        )
        .join(PracticeRun, PracticeRun.id == PracticeRunSection.run_id)
        .where(PracticeRun.perform_song_id == song_id)
    ).all()
    by_key: Dict[str, List[SectionResult]] = {}
    for key, practiced_at, stumbled in rows:
        by_key.setdefault(key, []).append(SectionResult(practiced_at, stumbled))
    overrides = {
        o.section_key: LevelOverride(level=o.level, set_at=o.set_at)
        for o in session.exec(
            select(SectionLevelOverride).where(
                SectionLevelOverride.perform_song_id == song_id
            )
        )
    }
    keys = sorted(set(by_key) | set(overrides))
    return {k: section_level(by_key.get(k, []), overrides.get(k)) for k in keys}


def set_override(
    session: Session, song_id: int, section_key: str, level: str
) -> SectionLevelOverride:
    validate_level(level)
    override = session.merge(
        SectionLevelOverride(
            perform_song_id=song_id,
            section_key=section_key,
            level=level,
            set_at=_utcnow(),
        )
    )
    session.commit()
    return override


def clear_override(session: Session, song_id: int, section_key: str) -> bool:
    override = session.get(SectionLevelOverride, (song_id, section_key))
    if override is None:
        return False
    session.delete(override)
    session.commit()
    return True


def rename_section(session: Session, song_id: int, from_key: str, to_key: str) -> int:
    """Move a section's history to a new label, after the sheet renamed it.

    A run that already has the new label keeps one row, stumbled if either
    was. Returns how many run rows were moved.

    If `from_key` has an override and `to_key` already has one too, the
    `to_key` override is left as it is and the `from_key` one is dropped:
    overrides are not merged the way run sections are."""
    if from_key == to_key:
        return 0
    run_ids = session.exec(
        select(PracticeRun.id).where(PracticeRun.perform_song_id == song_id)
    ).all()
    moved = 0
    if run_ids:
        rows = session.exec(
            select(PracticeRunSection)
            .where(PracticeRunSection.run_id.in_(run_ids))
            .where(PracticeRunSection.section_key == from_key)
        ).all()
        for row in rows:
            existing = session.get(PracticeRunSection, (row.run_id, to_key))
            if existing is not None:
                existing.stumbled = existing.stumbled or row.stumbled
                session.add(existing)
            else:
                session.add(
                    PracticeRunSection(
                        run_id=row.run_id,
                        section_key=to_key,
                        stumbled=row.stumbled,
                        position=row.position,
                    )
                )
            session.delete(row)
            moved += 1

    old = session.get(SectionLevelOverride, (song_id, from_key))
    if old is not None:
        if session.get(SectionLevelOverride, (song_id, to_key)) is None:
            session.add(
                SectionLevelOverride(
                    perform_song_id=song_id,
                    section_key=to_key,
                    level=old.level,
                    set_at=old.set_at,
                )
            )
        session.delete(old)
    session.commit()
    return moved


def runs_for_day(session: Session, dt: datetime) -> List[RunSummary]:
    """The runs of the calendar day `dt` falls on, in `dt`'s own timezone."""
    dt = pendulum.instance(dt)
    start = dt.start_of("day").in_timezone("UTC")
    end = dt.end_of("day").in_timezone("UTC")
    rows = session.exec(
        select(PracticeRun, PerformSong.name)
        .join(PerformSong, PerformSong.id == PracticeRun.perform_song_id)
        .where(PracticeRun.practiced_at >= start)
        .where(PracticeRun.practiced_at <= end)
        .order_by(PracticeRun.practiced_at)
    ).all()
    sections = sections_for_runs(session, [run.id for run, _ in rows])
    return [
        RunSummary(
            song_name=name,
            instrument=run.instrument,
            stumbled=[s.section_key for s in sections[run.id] if s.stumbled],
            practiced_at=run.practiced_at,
        )
        for run, name in rows
    ]
