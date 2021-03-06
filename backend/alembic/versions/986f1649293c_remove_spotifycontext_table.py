"""remove spotifycontext table

Revision ID: 986f1649293c
Revises: 7b7e1a7b6a0e
Create Date: 2022-04-23 10:31:47.083045

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '986f1649293c'
down_revision = '7b7e1a7b6a0e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # op.drop_table('spotifycontext')
    with op.batch_alter_table('spotifytrackhistory', schema=None) as batch_op:
        batch_op.add_column(sa.Column('context_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('context_type', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_spotifytrackhistory_context_name'), ['context_name'], unique=False)
        # batch_op.drop_constraint('fk_spotifytrackhistory_context_uri_spotifycontext', type_='foreignkey')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('spotifytrackhistory', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_spotifytrackhistory_context_uri_spotifycontext', 'spotifycontext', ['context_uri'], ['uri'])
        batch_op.drop_index(batch_op.f('ix_spotifytrackhistory_context_name'))
        batch_op.drop_column('context_type')
        batch_op.drop_column('context_name')

    op.create_table('spotifycontext',
    sa.Column('uri', sa.VARCHAR(), nullable=False),
    sa.Column('name', sa.VARCHAR(), nullable=True),
    sa.PrimaryKeyConstraint('uri', name='pk_spotifycontext')
    )
    # ### end Alembic commands ###
