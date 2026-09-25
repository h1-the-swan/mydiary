# -*- coding: utf-8 -*-

DESCRIPTION = """How well each section of a song is known, worked out from practice runs.

A section's level decides how much of it the practice sheet shows. It is never
stored: it is recomputed from the run history on every read, so changing the
thresholds here re-evaluates everything already recorded. Pure functions, no
I/O -- songs.py gathers the inputs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from .hashtags import slugify_tag

# from the most help to the least. the frontend mirrors these names in chordpro.ts
LEVELS = ("full", "letters", "cues", "memorized")
# clean runs in a row that move a section up one level
CLEAN_RUNS_TO_LEVEL_UP = 3


@dataclass(frozen=True)
class SectionResult:
    practiced_at: datetime
    stumbled: bool


@dataclass(frozen=True)
class LevelOverride:
    level: str
    set_at: datetime


@dataclass(frozen=True)
class SectionLevel:
    level: str
    clean_streak: int  # clean runs since the level last changed
    num_runs: int
    last_practiced_at: Optional[datetime]
    overridden: bool


def validate_level(level: str) -> str:
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; expected one of {LEVELS}")
    return level


def section_level(
    results: Iterable[SectionResult], override: Optional[LevelOverride] = None
) -> SectionLevel:
    """Replay a section's runs, oldest first, from `full` (or from an override).

    A stumble only brings the hints back one step, and three clean runs take
    them away again, so one bad day costs little."""
    ordered = sorted(results, key=lambda r: r.practiced_at)
    idx = 0
    counted = ordered
    if override is not None:
        idx = LEVELS.index(validate_level(override.level))
        counted = [r for r in ordered if r.practiced_at > override.set_at]

    streak = 0
    for r in counted:
        if r.stumbled:
            idx = max(idx - 1, 0)
            streak = 0
            continue
        streak += 1
        if streak >= CLEAN_RUNS_TO_LEVEL_UP and idx < len(LEVELS) - 1:
            idx += 1
            streak = 0

    return SectionLevel(
        level=LEVELS[idx],
        clean_streak=streak,
        num_runs=len(ordered),
        last_practiced_at=ordered[-1].practiced_at if ordered else None,
        overridden=override is not None,
    )


@dataclass(frozen=True)
class RunSummary:
    song_name: str
    instrument: Optional[str]  # None for practice away from the instrument
    stumbled: List[str]  # section keys, in sheet order
    practiced_at: datetime


def song_ref(song_name: str) -> str:
    """`#song:<slug>`, so the diary line links to the song through the tag system.

    Falls back to the bare name for a title with nothing slug-shaped in it."""
    try:
        return f"#song:{slugify_tag(song_name)}"
    except ValueError:
        return song_name


def run_line(run: RunSummary) -> str:
    where = run.instrument or "lyrics only"
    if run.stumbled:
        result = "stumbled on " + ", ".join(run.stumbled)
    else:
        result = "clean run"
    return f"- {song_ref(run.song_name)}, {where}: {result}"


def practice_markdown(runs: Iterable[RunSummary]) -> str:
    runs = sorted(runs, key=lambda r: r.practiced_at)
    if not runs:
        return "None"
    return "\n".join(run_line(r) for r in runs)
