"""rename partner_id to org_id in partner table

Revision ID: 32847829b9f1
Revises: e6ca46c5c84c
Create Date: 2025-11-24 17:25:50.290051

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32847829b9f1'
down_revision: Union[str, Sequence[str], None] = 'e6ca46c5c84c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "partner",
        "partner_id",
        new_column_name="org_id",
        schema="partner",
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
