"""add unique constraint joplin note title

Revision ID: 0807f083f83f
Revises: 972ada4bfca5
Create Date: 2024-12-28 15:29:33.789418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '0807f083f83f'
down_revision: Union[str, None] = '972ada4bfca5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('joplinnote', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['title'])

    with op.batch_alter_table('mydiarywords', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'joplinnote', ['joplin_note_id'], ['id'])

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('mydiarywords', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('joplinnote', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    # ### end Alembic commands ###