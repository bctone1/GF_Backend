"""colour

Revision ID: af8a4f9def66
Revises: a9f6d3087463
Create Date: 2026-02-05 15:58:24.377227

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af8a4f9def66'
down_revision: Union[str, Sequence[str], None] = 'a9f6d3087463'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_prompts",
        sa.Column("color", sa.Text(), nullable=True),
        schema="user",
    )


def downgrade() -> None:
    op.drop_column("ai_prompts", "color", schema="user")