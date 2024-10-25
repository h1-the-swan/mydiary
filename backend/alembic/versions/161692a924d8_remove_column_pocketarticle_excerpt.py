"""remove column PocketArticle.excerpt

Revision ID: 161692a924d8
Revises: 1e4c09f9bc6e
Create Date: 2024-09-10 13:14:44.188062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '161692a924d8'
down_revision: Union[str, None] = '1e4c09f9bc6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('pocketarticle', 'excerpt')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('pocketarticle', sa.Column('excerpt', sa.VARCHAR(), nullable=True))
    # ### end Alembic commands ###
