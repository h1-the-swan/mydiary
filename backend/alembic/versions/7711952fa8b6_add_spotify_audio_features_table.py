"""add spotify audio features table

Revision ID: 7711952fa8b6
Revises: 54bc67175129
Create Date: 2025-02-25 15:04:14.354355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '7711952fa8b6'
down_revision: Union[str, None] = '54bc67175129'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('spotifytrackhistoryaudiofeatures',
    sa.Column('spotify_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('acousticness', sa.Float(), nullable=False),
    sa.Column('danceability', sa.Float(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('energy', sa.Float(), nullable=False),
    sa.Column('instrumentalness', sa.Float(), nullable=False),
    sa.Column('key', sa.Integer(), nullable=False),
    sa.Column('liveness', sa.Float(), nullable=False),
    sa.Column('mode', sa.Integer(), nullable=False),
    sa.Column('speechiness', sa.Float(), nullable=False),
    sa.Column('tempo', sa.Float(), nullable=False),
    sa.Column('time_signature', sa.Integer(), nullable=False),
    sa.Column('valence', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['spotify_id'], ['spotifytrack.spotify_id'], ),
    sa.PrimaryKeyConstraint('spotify_id')
    )
    with op.batch_alter_table('spotifytrackhistoryaudiofeatures', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_acousticness'), ['acousticness'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_danceability'), ['danceability'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_duration_ms'), ['duration_ms'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_energy'), ['energy'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_instrumentalness'), ['instrumentalness'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_key'), ['key'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_liveness'), ['liveness'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_mode'), ['mode'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_speechiness'), ['speechiness'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_tempo'), ['tempo'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_time_signature'), ['time_signature'], unique=False)
        batch_op.create_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_valence'), ['valence'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('spotifytrackhistoryaudiofeatures', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_valence'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_time_signature'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_tempo'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_speechiness'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_mode'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_liveness'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_key'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_instrumentalness'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_energy'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_duration_ms'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_danceability'))
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistoryaudiofeatures_acousticness'))

    op.drop_table('spotifytrackhistoryaudiofeatures')
    # ### end Alembic commands ###
