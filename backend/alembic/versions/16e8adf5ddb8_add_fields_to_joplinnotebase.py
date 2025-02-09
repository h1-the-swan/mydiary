"""add fields to joplinnotebase

Revision ID: 16e8adf5ddb8
Revises: de39eddb61af
Create Date: 2025-01-04 14:51:33.201571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '16e8adf5ddb8'
down_revision: Union[str, None] = 'de39eddb61af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('joplinnote', schema=None) as batch_op:
        batch_op.add_column(sa.Column('body_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('has_words', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('has_images', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.create_index(batch_op.f('ix_joplinnote_body_hash'), ['body_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_joplinnote_has_images'), ['has_images'], unique=False)
        batch_op.create_index(batch_op.f('ix_joplinnote_has_words'), ['has_words'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('joplinnote', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_joplinnote_has_words'))
        batch_op.drop_index(batch_op.f('ix_joplinnote_has_images'))
        batch_op.drop_index(batch_op.f('ix_joplinnote_body_hash'))
        batch_op.drop_column('has_images')
        batch_op.drop_column('has_words')
        batch_op.drop_column('body_hash')

    # ### end Alembic commands ###
