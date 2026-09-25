# -*- coding: utf-8 -*-
"""The tags migration, run by the real alembic against the old table shapes.

The migration history cannot build the schema from nothing (the root revision
is empty), so the pre-tags tables are created here by hand, exactly as
create_all() used to make them, and alembic is stamped at the revision before
the tags migration. alembic runs as a subprocess with MYDIARY_ROOTDIR pointing
at a temp dir, which is how db.py finds the database (and how env.py does)."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
BEFORE_TAGS_REVISION = "40e2fef86acd"

OLD_SCHEMA = """
CREATE TABLE tag (
    name VARCHAR NOT NULL,
    is_pocket_tag BOOLEAN NOT NULL,
    PRIMARY KEY (name)
);
CREATE INDEX ix_tag_is_pocket_tag ON tag (is_pocket_tag);
CREATE TABLE pocketarticletaglink (
    article_id INTEGER NOT NULL,
    tag_name VARCHAR NOT NULL,
    PRIMARY KEY (article_id, tag_name),
    FOREIGN KEY(article_id) REFERENCES pocketarticle (id),
    FOREIGN KEY(tag_name) REFERENCES tag (name)
);
CREATE TABLE recipetaglink (
    recipe_id INTEGER NOT NULL,
    tag_name VARCHAR NOT NULL,
    PRIMARY KEY (recipe_id, tag_name),
    FOREIGN KEY(recipe_id) REFERENCES recipe (id),
    FOREIGN KEY(tag_name) REFERENCES tag (name)
);
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
"""

# the shapes found in the real data: spaces, dots, a colon, a URL, digits,
# and a pair that slugify to the same thing
OLD_TAGS = [
    "internet",
    "saved for later",
    "a.v. club",
    "re:read",
    "A B",
    "a-b",
    "https://savage.love",
    "2024",
]
OLD_ARTICLE_LINKS = [
    (1, "internet"),
    (1, "saved for later"),
    (2, "internet"),
    (2, "A B"),
    (2, "a-b"),
    (3, "ghost"),  # an orphan: no such tag row (FKs were never enforced)
]
OLD_RECIPE_LINKS = [(1, "internet")]


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
    return [row[1] for row in query(rootdir, f"PRAGMA table_info({table})")]


@pytest.fixture
def old_db(tmp_path: Path) -> Path:
    con = sqlite3.connect(tmp_path / "database.db")
    with con:
        con.executescript(OLD_SCHEMA)
        con.executemany("INSERT INTO tag VALUES (?, 1)", [(t,) for t in OLD_TAGS])
        con.executemany("INSERT INTO pocketarticletaglink VALUES (?, ?)", OLD_ARTICLE_LINKS)
        con.executemany("INSERT INTO recipetaglink VALUES (?, ?)", OLD_RECIPE_LINKS)
        con.execute("INSERT INTO alembic_version VALUES (?)", (BEFORE_TAGS_REVISION,))
    con.close()
    return tmp_path


class TestUpgrade:
    def test_tags_are_normalised_and_links_carried_over(self, old_db: Path):
        run_or_fail(old_db, "upgrade", "head")

        assert query(old_db, "SELECT version_num FROM alembic_version") != [(BEFORE_TAGS_REVISION,)]
        assert set(columns(old_db, "tag")) == {"id", "namespace", "slug", "name", "created_at"}
        assert set(columns(old_db, "taglink")) == {"tag_id", "target_type", "target_id", "source", "created_at"}
        for gone in ("pocketarticletaglink", "recipetaglink", "tag_new"):
            assert query(old_db, "SELECT name FROM sqlite_master WHERE name = ?", (gone,)) == []

        tags = {name: (namespace, slug) for name, namespace, slug in query(old_db, "SELECT name, namespace, slug FROM tag")}
        # every old tag survives with its display name, plus the orphan link's tag
        assert set(tags) == set(OLD_TAGS) | {"ghost"}
        assert all(ns == "" for ns, _ in tags.values())
        assert tags["saved for later"][1] == "saved-for-later"
        assert tags["a.v. club"][1] == "a-v-club"
        assert tags["re:read"][1] == "re-read"  # a colon in an imported name is not a namespace
        assert tags["https://savage.love"][1] == "https-savage-love"
        assert tags["2024"][1] == "2024"
        assert {tags["A B"][1], tags["a-b"][1]} == {"a-b", "a-b-2"}
        assert len({v for v in tags.values()}) == len(tags)  # (namespace, slug) unique

        links = query(old_db, "SELECT t.name, l.target_type, l.target_id, l.source FROM taglink l JOIN tag t ON t.id = l.tag_id ORDER BY l.target_type, l.target_id, t.name")
        assert links == [
            ("internet", "article", "1", "pocket"),
            ("saved for later", "article", "1", "pocket"),
            ("A B", "article", "2", "pocket"),
            ("a-b", "article", "2", "pocket"),
            ("internet", "article", "2", "pocket"),
            ("ghost", "article", "3", "pocket"),
            ("internet", "recipe", "1", "manual"),
        ]
        assert all(row[0] for row in query(old_db, "SELECT created_at FROM taglink"))

        index_names = {row[0] for row in query(old_db, "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name IN ('tag', 'taglink')")}
        assert {"ix_tag_namespace", "ix_tag_slug", "ix_taglink_target", "ix_taglink_source"} <= index_names
        assert query(old_db, "SELECT sql FROM sqlite_master WHERE name = 'tag'")[0][0].count("uix_tag_namespace_slug") == 1

    def test_a_leftover_from_a_failed_run_does_not_block_a_rerun(self, old_db: Path):
        # DDL runs outside the transaction in pysqlite, so a failure midway
        # leaves tag_new behind; the migration must clear it first
        con = sqlite3.connect(old_db / "database.db")
        with con:
            con.execute("CREATE TABLE tag_new (id INTEGER PRIMARY KEY, junk TEXT)")
        con.close()
        run_or_fail(old_db, "upgrade", "head")
        assert "junk" not in columns(old_db, "tag")


class TestDowngrade:
    def test_round_trip_restores_the_old_shape(self, old_db: Path):
        run_or_fail(old_db, "upgrade", "head")
        run_or_fail(old_db, "downgrade", BEFORE_TAGS_REVISION)

        assert query(old_db, "SELECT version_num FROM alembic_version") == [(BEFORE_TAGS_REVISION,)]
        assert columns(old_db, "tag") == ["name", "is_pocket_tag"]
        assert set(columns(old_db, "pocketarticletaglink")) == {"article_id", "tag_name"}
        assert set(columns(old_db, "recipetaglink")) == {"recipe_id", "tag_name"}
        assert query(old_db, "SELECT name FROM sqlite_master WHERE name = 'taglink'") == []

        names = {row[0] for row in query(old_db, "SELECT name FROM tag")}
        assert names == set(OLD_TAGS) | {"ghost"}
        assert sorted(query(old_db, "SELECT article_id, tag_name FROM pocketarticletaglink")) == sorted(OLD_ARTICLE_LINKS)
        assert query(old_db, "SELECT recipe_id, tag_name FROM recipetaglink") == OLD_RECIPE_LINKS
        # is_pocket_tag means "has an article link"
        pocket_flags = dict(query(old_db, "SELECT name, is_pocket_tag FROM tag"))
        assert pocket_flags["internet"] == 1
        assert pocket_flags["2024"] == 0

        # and up again, cleanly
        run_or_fail(old_db, "upgrade", "head")
        assert query(old_db, "SELECT count(*) FROM taglink") == [(7,)]
