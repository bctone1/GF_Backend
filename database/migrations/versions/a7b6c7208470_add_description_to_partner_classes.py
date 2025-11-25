"""add_description_to_partner_classes

Revision ID: a7b6c7208470
Revises: 459ada250577
Create Date: 2025-11-25 14:53:52.398363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b6c7208470'
down_revision: Union[str, Sequence[str], None] = '459ada250577'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "classes",
        sa.Column("description", sa.Text(), nullable=True),
        schema="partner",
    )


def downgrade() -> None:
    op.drop_column("classes", "description", schema="partner")
