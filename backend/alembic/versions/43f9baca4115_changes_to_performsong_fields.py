"""changes to performsong fields

Revision ID: 43f9baca4115
Revises: afdb51149db4
Create Date: 2022-07-19 16:38:47.431101

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '43f9baca4115'
down_revision = 'afdb51149db4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('performsong', schema=None) as batch_op:
        batch_op.alter_column('artist_name',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.alter_column('learned',
               existing_type=sa.BOOLEAN(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('performsong', schema=None) as batch_op:
        batch_op.alter_column('learned',
               existing_type=sa.BOOLEAN(),
               nullable=False)
        batch_op.alter_column('artist_name',
               existing_type=sa.VARCHAR(),
               nullable=False)

    # ### end Alembic commands ###