"""make_course

Revision ID: 459ada250577
Revises: 7c6e1000f858
Create Date: 2025-11-25 14:49:19.429826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '459ada250577'
down_revision: Union[str, Sequence[str], None] = '7c6e1000f858'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
