"""add key and capo columns to performsongs table

Revision ID: afdb51149db4
Revises: 72c1841ec029
Create Date: 2022-07-04 18:53:11.087996

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'afdb51149db4'
down_revision = '72c1841ec029'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('performsong', schema=None) as batch_op:
        batch_op.add_column(sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('capo', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_performsong_capo'), ['capo'], unique=False)
        batch_op.create_index(batch_op.f('ix_performsong_key'), ['key'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('performsong', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_performsong_key'))
        batch_op.drop_index(batch_op.f('ix_performsong_capo'))
        batch_op.drop_column('capo')
        batch_op.drop_column('key')

    # ### end Alembic commands ###
