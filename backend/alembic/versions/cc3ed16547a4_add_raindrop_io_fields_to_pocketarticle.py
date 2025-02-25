"""add raindrop.io fields to PocketArticle

Revision ID: cc3ed16547a4
Revises: 1d0994fb3e88
Create Date: 2024-12-09 18:43:13.694733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc3ed16547a4'
down_revision: Union[str, None] = '1d0994fb3e88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('pocketarticle', sa.Column('raindrop_id', sa.Integer(), nullable=True))
    op.add_column('pocketarticle', sa.Column('time_pocket_raindrop_sync', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_pocketarticle_raindrop_id'), 'pocketarticle', ['raindrop_id'], unique=False)
    op.create_index(op.f('ix_pocketarticle_time_pocket_raindrop_sync'), 'pocketarticle', ['time_pocket_raindrop_sync'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_pocketarticle_time_pocket_raindrop_sync'), table_name='pocketarticle')
    op.drop_index(op.f('ix_pocketarticle_raindrop_id'), table_name='pocketarticle')
    op.drop_column('pocketarticle', 'time_pocket_raindrop_sync')
    op.drop_column('pocketarticle', 'raindrop_id')
    # ### end Alembic commands ###
