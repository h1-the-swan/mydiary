"""PerformSong Added and Learned dates become calendar dates

Revision ID: 9ecbdf140eb4
Revises: 64fa81d8c2b8
Create Date: 2026-09-30 09:00:00.000000

created_at -> added_date and learned_dt -> learned_date, DATETIME -> DATE.
Each value keeps its stored date digits ('2021-01-15 00:19:10.000000' ->
'2021-01-15'), which is the day the pages showed.

Written by hand as add, copy, drop. Don't turn it into alter_column with
type_=sa.Date(): on SQLite, batch mode copies the rows through
CAST(col AS DATE), and SQLite casts '2021-01-15' to the integer 2021.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ecbdf140eb4'
down_revision: Union[str, None] = '64fa81d8c2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (old DATETIME column, new DATE column)
RENAMES = [("created_at", "added_date"), ("learned_dt", "learned_date")]


def _columns() -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("performsong")}


def upgrade() -> None:
    # DDL isn't transactional here, so a failed run can leave a new column behind
    existing = _columns()
    for old, new in RENAMES:
        if new not in existing:
            op.add_column("performsong", sa.Column(new, sa.Date(), nullable=True))
        op.execute(
            f"UPDATE performsong SET {new} = substr({old}, 1, 10) WHERE {old} IS NOT NULL"
        )
    with op.batch_alter_table("performsong") as batch_op:
        for old, _ in RENAMES:
            batch_op.drop_index(f"ix_performsong_{old}")
            batch_op.drop_column(old)
    # outside the batch block: creating them inside it fails on the new columns
    for _, new in RENAMES:
        op.create_index(f"ix_performsong_{new}", "performsong", [new])


def downgrade() -> None:
    existing = _columns()
    for old, new in RENAMES:
        if old not in existing:
            op.add_column("performsong", sa.Column(old, sa.DateTime(), nullable=True))
        op.execute(
            f"UPDATE performsong SET {old} = {new} || ' 00:00:00.000000' WHERE {new} IS NOT NULL"
        )
    with op.batch_alter_table("performsong") as batch_op:
        for old, new in RENAMES:
            batch_op.drop_index(f"ix_performsong_{new}")
            batch_op.drop_column(new)
    for old, _ in RENAMES:
        op.create_index(f"ix_performsong_{old}", "performsong", [old])
