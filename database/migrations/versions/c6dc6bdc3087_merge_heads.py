"""merge_heads

Revision ID: c6dc6bdc3087
Revises: 3b0b0b3d4b7d, 335e33882fba
Create Date: 2026-01-27 13:28:30.562838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6dc6bdc3087'
down_revision: Union[str, Sequence[str], None] = ('3b0b0b3d4b7d', '335e33882fba')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
