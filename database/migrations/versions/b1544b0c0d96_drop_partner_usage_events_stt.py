"""drop partner.usage_events_stt

Revision ID: b1544b0c0d96
Revises: 72dd40c64d15
Create Date: 2026-01-07 17:22:39.292426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1544b0c0d96'
down_revision: Union[str, Sequence[str], None] = '72dd40c64d15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS partner.usage_events_stt")

def downgrade() -> None:
    """Downgrade schema."""
    pass
