"""owntracks day maps: one row per map panel

A day spent in two or more distinct areas gets several maps -- the whole-day
overview plus one panel per area -- so diary_date alone can no longer be the
primary key. Autogenerate only saw the added column: SQLite cannot alter a
primary key in place, so the table is rebuilt by hand and existing rows become
panel 0, the overview, which is what they already were.

Revision ID: 40e2fef86acd
Revises: fd9d21eb39d6
Create Date: 2026-08-16 14:19:04.134461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '40e2fef86acd'
down_revision: Union[str, None] = 'fd9d21eb39d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = (
    "diary_date",
    "joplin_resource_id",
    "content_hash",
    "num_points",
    "num_stays",
    "distance_m",
    "created_at",
)


def upgrade() -> None:
    op.rename_table("owntracksdaymap", "owntracksdaymap_old")
    op.create_table(
        "owntracksdaymap",
        sa.Column("diary_date", sa.Date(), nullable=False),
        sa.Column("panel", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("joplin_resource_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("num_points", sa.Integer(), nullable=False),
        sa.Column("num_stays", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("diary_date", "panel", name="pk_owntracksdaymap"),
    )
    columns = ", ".join(COLUMNS)
    op.execute(
        f"INSERT INTO owntracksdaymap (panel, {columns}) "
        f"SELECT 0, {columns} FROM owntracksdaymap_old"
    )
    # dropping the old table takes its copy of the index name with it, so the
    # new index can only be created afterwards
    op.drop_table("owntracksdaymap_old")
    op.create_index(
        op.f("ix_owntracksdaymap_content_hash"),
        "owntracksdaymap",
        ["content_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.rename_table("owntracksdaymap", "owntracksdaymap_new")
    op.create_table(
        "owntracksdaymap",
        sa.Column("diary_date", sa.Date(), nullable=False),
        sa.Column("joplin_resource_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("num_points", sa.Integer(), nullable=False),
        sa.Column("num_stays", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("diary_date", name="pk_owntracksdaymap"),
    )
    columns = ", ".join(COLUMNS)
    # the area panels have nowhere to go in a one-row-per-day table; only the
    # overview survives, and the notes keep their now-unbookkept area images
    op.execute(
        f"INSERT INTO owntracksdaymap ({columns}) "
        f"SELECT {columns} FROM owntracksdaymap_new WHERE panel = 0"
    )
    op.drop_table("owntracksdaymap_new")
    op.create_index(
        op.f("ix_owntracksdaymap_content_hash"),
        "owntracksdaymap",
        ["content_hash"],
        unique=False,
    )
