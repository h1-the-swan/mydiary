"""tags overhaul: namespaced tags and one polymorphic link table

Tags become `#namespace:slug` (see mydiary/hashtags.py). The old `tag` table
keyed by name is rebuilt with a surrogate id, a namespace (empty string for
none), a slug and a display name, and the two per-type link tables are folded
into one `taglink` keyed by (tag_id, target_type, target_id) with a `source`.

SQLite cannot change a primary key in place, and it rewrites foreign-key
references in *other* tables when a table is renamed, so the order matters:
build `tag_new` and stage the link rows in memory, drop the old link tables
and `tag`, rename, and only then create `taglink` so its FK points at the new
`tag`. pysqlite runs DDL outside the transaction, so `tag_new` is dropped
first in case a previous run failed midway.

Existing tags all came from Pocket. Each keeps its name as the display label
and gets a slug derived from it (collisions get a -2, -3 suffix; a colon in an
imported name is not a namespace). Article links become source="pocket",
recipe links "manual". A link whose tag row is missing gets its tag created,
since the FK was never enforced.

Downgrade restores the old shape from the article and recipe links. Links
made since to days, songs or dogs have nowhere to go and are dropped.

Revision ID: 0652a2a11ff2
Revises: 40e2fef86acd
Create Date: 2026-09-18

"""
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Sequence, Set, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from mydiary.hashtags import slugify_tag, tag_key


# revision identifiers, used by Alembic.
revision: str = "0652a2a11ff2"
down_revision: Union[str, None] = "40e2fef86acd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _now() -> datetime:
    # what SQLite ends up holding for the models' pendulum.now("UTC") defaults
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _unique_slug(name: str, used: Set[str]) -> str:
    try:
        base = slugify_tag(name)
    except ValueError:
        base = "tag"
    slug, n = base, 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def upgrade() -> None:
    bind = op.get_bind()
    now = _now()

    op.execute("DROP TABLE IF EXISTS tag_new")
    op.create_table(
        "tag_new",
        sa.Column("namespace", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace", "slug", name="uix_tag_namespace_slug"),
    )

    used_slugs: Set[str] = set()
    ids_by_name: Dict[str, int] = {}

    def insert_tag(name: str) -> None:
        slug = _unique_slug(name, used_slugs)
        result = bind.execute(
            sa.text(
                "INSERT INTO tag_new (namespace, slug, name, created_at) "
                "VALUES ('', :slug, :name, :now)"
            ),
            {"slug": slug, "name": name, "now": now},
        )
        ids_by_name[name] = result.lastrowid

    for (name,) in bind.execute(sa.text("SELECT name FROM tag ORDER BY rowid")):
        insert_tag(name)

    staged: List[dict] = []
    link_sources = [
        ("pocketarticletaglink", "article_id", "article", "pocket"),
        ("recipetaglink", "recipe_id", "recipe", "manual"),
    ]
    for table, id_column, target_type, source in link_sources:
        rows = bind.execute(
            sa.text(f"SELECT {id_column}, tag_name FROM {table} ORDER BY rowid")
        ).fetchall()
        for target_id, tag_name in rows:
            if tag_name not in ids_by_name:
                insert_tag(tag_name)  # orphan link: the FK was never enforced
            staged.append(
                {
                    "tag_id": ids_by_name[tag_name],
                    "target_type": target_type,
                    "target_id": str(target_id),
                    "source": source,
                    "created_at": now,
                }
            )
    expected_links = len(staged)

    # the old link tables reference tag by name; they go before the rename so
    # SQLite has nothing to rewrite
    op.drop_table("pocketarticletaglink")
    op.drop_table("recipetaglink")
    op.drop_table("tag")
    op.rename_table("tag_new", "tag")

    op.create_table(
        "taglink",
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"]),
        sa.PrimaryKeyConstraint("tag_id", "target_type", "target_id"),
    )
    if staged:
        taglink = sa.table(
            "taglink",
            sa.column("tag_id", sa.Integer),
            sa.column("target_type", sa.String),
            sa.column("target_id", sa.String),
            sa.column("source", sa.String),
            sa.column("created_at", sa.DateTime),
        )
        op.bulk_insert(taglink, staged)

    op.create_index("ix_tag_namespace", "tag", ["namespace"])
    op.create_index("ix_tag_slug", "tag", ["slug"])
    op.create_index("ix_tag_created_at", "tag", ["created_at"])
    op.create_index("ix_taglink_target_type", "taglink", ["target_type"])
    op.create_index("ix_taglink_target_id", "taglink", ["target_id"])
    op.create_index("ix_taglink_source", "taglink", ["source"])
    op.create_index("ix_taglink_created_at", "taglink", ["created_at"])
    op.create_index("ix_taglink_target", "taglink", ["target_type", "target_id"])

    actual_links = bind.execute(sa.text("SELECT count(*) FROM taglink")).scalar()
    if actual_links != expected_links:
        raise RuntimeError(
            f"taglink has {actual_links} rows, expected {expected_links}; refusing to finish"
        )


def downgrade() -> None:
    bind = op.get_bind()

    tags = bind.execute(
        sa.text("SELECT id, namespace, slug, name FROM tag ORDER BY id")
    ).fetchall()
    links = bind.execute(
        sa.text(
            "SELECT tag_id, target_type, target_id FROM taglink "
            "WHERE target_type IN ('article', 'recipe') ORDER BY rowid"
        )
    ).fetchall()

    # the old key was the name; where two tags share one, fall back to the key
    name_counts = Counter(name for _, _, _, name in tags)
    old_name = {
        tag_id: (name if name_counts[name] == 1 else tag_key(namespace, slug))
        for tag_id, namespace, slug, name in tags
    }
    pocket_tag_ids = {tag_id for tag_id, target_type, _ in links if target_type == "article"}

    op.execute("DROP TABLE IF EXISTS tag_old")
    op.create_table(
        "tag_old",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_pocket_tag", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    tag_old = sa.table(
        "tag_old", sa.column("name", sa.String), sa.column("is_pocket_tag", sa.Boolean)
    )
    op.bulk_insert(
        tag_old,
        [
            {"name": old_name[tag_id], "is_pocket_tag": tag_id in pocket_tag_ids}
            for tag_id, _, _, _ in tags
        ],
    )

    op.drop_table("taglink")
    op.drop_table("tag")
    op.rename_table("tag_old", "tag")
    op.create_index("ix_tag_is_pocket_tag", "tag", ["is_pocket_tag"])

    op.create_table(
        "pocketarticletaglink",
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("tag_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["pocketarticle.id"]),
        sa.ForeignKeyConstraint(["tag_name"], ["tag.name"]),
        sa.PrimaryKeyConstraint("article_id", "tag_name"),
    )
    op.create_table(
        "recipetaglink",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("tag_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"]),
        sa.ForeignKeyConstraint(["tag_name"], ["tag.name"]),
        sa.PrimaryKeyConstraint("recipe_id", "tag_name"),
    )
    for table, id_column, target_type in [
        ("pocketarticletaglink", "article_id", "article"),
        ("recipetaglink", "recipe_id", "recipe"),
    ]:
        rows = {
            (int(target_id), old_name[tag_id])
            for tag_id, tt, target_id in links
            if tt == target_type
        }
        if rows:
            op.bulk_insert(
                sa.table(
                    table, sa.column(id_column, sa.Integer), sa.column("tag_name", sa.String)
                ),
                [{id_column: i, "tag_name": n} for i, n in sorted(rows)],
            )
