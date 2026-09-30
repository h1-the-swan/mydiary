# -*- coding: utf-8 -*-
"""The PerformSong calendar-dates migration, run by the real alembic.

As in test_migration_tags.py, the old performsong table is built here by hand
(as create_all() made it) and alembic is stamped at the revision before the
migration, then run as a subprocess against a temp MYDIARY_ROOTDIR."""

import os
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine, select

from mydiary.models import PerformSong

BACKEND_DIR = Path(__file__).resolve().parents[1]
BEFORE_REVISION = "64fa81d8c2b8"
# the migration under test, not head, so later migrations can't break this test
REVISION = "9ecbdf140eb4"

OLD_SCHEMA = """
CREATE TABLE spotifytrack (
    spotify_id VARCHAR NOT NULL,
    PRIMARY KEY (spotify_id)
);
CREATE TABLE performsong (
    name VARCHAR NOT NULL,
    artist_name VARCHAR,
    learned BOOLEAN NOT NULL,
    spotify_id VARCHAR,
    notes VARCHAR,
    perform_url VARCHAR,
    created_at DATETIME,
    "key" VARCHAR,
    capo INTEGER,
    lyrics VARCHAR,
    learned_dt DATETIME,
    id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(spotify_id) REFERENCES spotifytrack (spotify_id)
);
CREATE INDEX ix_performsong_name ON performsong (name);
CREATE INDEX ix_performsong_created_at ON performsong (created_at);
CREATE INDEX ix_performsong_learned_dt ON performsong (learned_dt);
CREATE TABLE child (
    id INTEGER NOT NULL PRIMARY KEY,
    perform_song_id INTEGER NOT NULL,
    FOREIGN KEY(perform_song_id) REFERENCES performsong (id)
);
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
"""

# (id, name, created_at, learned_dt): the stored shapes found in real data,
# on made-up songs
OLD_ROWS = [
    (1, "Midnight Song", "2020-01-15 00:00:00.000000", "2020-01-15 00:00:00.000000"),
    (2, "Import Song", "2021-03-04 04:00:00.000000", "2021-03-04 04:00:00.000000"),
    (3, "Early Song", "2022-07-08 00:19:10.000000", None),
    (4, "Afternoon Song", "2026-09-27 16:00:32.244000", "2026-09-28 23:59:59.999999"),
    (5, "Undated Song", None, None),
]


def expected_dates():
    return [
        (i, created[:10] if created else None, learned[:10] if learned else None)
        for i, _, created, learned in OLD_ROWS
    ]


def alembic(rootdir: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "MYDIARY_ROOTDIR": str(rootdir)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def run_or_fail(rootdir: Path, *args: str) -> None:
    proc = alembic(rootdir, *args)
    assert proc.returncode == 0, f"alembic {' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}"


def query(rootdir: Path, sql: str, params=()):
    con = sqlite3.connect(rootdir / "database.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def columns(rootdir: Path, table: str):
    return {row[1]: row[2] for row in query(rootdir, f"PRAGMA table_info({table})")}


def indexes(rootdir: Path):
    return {row[0] for row in query(rootdir, "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'performsong'")}


@pytest.fixture
def old_db(tmp_path: Path) -> Path:
    con = sqlite3.connect(tmp_path / "database.db")
    with con:
        con.executescript(OLD_SCHEMA)
        con.executemany(
            "INSERT INTO performsong (id, name, learned, created_at, learned_dt) VALUES (?, ?, 1, ?, ?)",
            OLD_ROWS,
        )
        con.execute("INSERT INTO child VALUES (1, 4)")
        con.execute("INSERT INTO alembic_version VALUES (?)", (BEFORE_REVISION,))
    con.close()
    return tmp_path


class TestUpgrade:
    def test_dates_keep_their_date_digits(self, old_db: Path):
        run_or_fail(old_db, "upgrade", REVISION)

        cols = columns(old_db, "performsong")
        assert cols["added_date"] == "DATE"
        assert cols["learned_date"] == "DATE"
        assert "created_at" not in cols and "learned_dt" not in cols

        rows = query(old_db, "SELECT id, added_date, learned_date FROM performsong ORDER BY id")
        assert rows == expected_dates()
        # text, not a number: a CAST to DATE would have left the integer year
        types = query(old_db, "SELECT DISTINCT typeof(added_date), typeof(learned_date) FROM performsong WHERE id != 5")
        assert {t for pair in types for t in pair if t != "null"} == {"text"}

        assert {"ix_performsong_added_date", "ix_performsong_learned_date", "ix_performsong_name"} <= indexes(old_db)
        assert not {"ix_performsong_created_at", "ix_performsong_learned_dt"} & indexes(old_db)

        # the table rebuild keeps rows that point at a PerformSong valid
        assert query(old_db, "SELECT perform_song_id FROM child") == [(4,)]
        assert query(old_db, "PRAGMA foreign_key_check(child)") == []

    def test_the_model_reads_the_migrated_rows(self, old_db: Path):
        run_or_fail(old_db, "upgrade", REVISION)
        engine = create_engine(f"sqlite:///{old_db / 'database.db'}")
        with Session(engine) as session:
            songs = {s.id: s for s in session.exec(select(PerformSong))}
        engine.dispose()
        assert songs[3].added_date == date(2022, 7, 8)
        assert songs[3].learned_date is None
        assert songs[4].learned_date == date(2026, 9, 28)
        assert songs[5].added_date is None

    def test_a_leftover_column_from_a_failed_run_does_not_block_a_rerun(self, old_db: Path):
        con = sqlite3.connect(old_db / "database.db")
        with con:
            con.execute("ALTER TABLE performsong ADD COLUMN added_date DATE")
        con.close()
        run_or_fail(old_db, "upgrade", REVISION)
        rows = query(old_db, "SELECT id, added_date, learned_date FROM performsong ORDER BY id")
        assert rows == expected_dates()


class TestDowngrade:
    def test_round_trip_restores_the_old_shape(self, old_db: Path):
        run_or_fail(old_db, "upgrade", REVISION)
        run_or_fail(old_db, "downgrade", BEFORE_REVISION)

        assert query(old_db, "SELECT version_num FROM alembic_version") == [(BEFORE_REVISION,)]
        cols = columns(old_db, "performsong")
        assert cols["created_at"] == "DATETIME"
        assert cols["learned_dt"] == "DATETIME"
        assert "added_date" not in cols and "learned_date" not in cols
        assert {"ix_performsong_created_at", "ix_performsong_learned_dt"} <= indexes(old_db)

        # the time of day is gone for good; the date comes back at midnight
        rows = query(old_db, "SELECT id, created_at, learned_dt FROM performsong ORDER BY id")
        assert rows == [
            (i, a and f"{a} 00:00:00.000000", l and f"{l} 00:00:00.000000")
            for i, a, l in expected_dates()
        ]

        # and up again, cleanly
        run_or_fail(old_db, "upgrade", REVISION)
        assert query(old_db, "SELECT id, added_date, learned_date FROM performsong ORDER BY id") == expected_dates()
