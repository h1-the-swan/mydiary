"""add column to dog table

Revision ID: abae23bcb70a
Revises: 8c914034989f
Create Date: 2022-05-01 13:19:05.691428

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'abae23bcb70a'
down_revision = '8c914034989f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dog', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dog', schema=None) as batch_op:
        batch_op.drop_column('notes')

    # ### end Alembic commands ###