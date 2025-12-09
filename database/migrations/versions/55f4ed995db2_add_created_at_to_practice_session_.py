"""add created_at to practice_session_models and notes to practice_sessions

Revision ID: 55f4ed995db2
Revises: 2fd72a73adc7
Create Date: 2025-12-09 14:14:22.868701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55f4ed995db2'
down_revision: Union[str, Sequence[str], None] = '2fd72a73adc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ⚠️ practice_sessions.notes 는 이미 존재하므로 건드리지 말기

    # 1) user.practice_session_models.created_at 추가
    op.add_column(
        "practice_session_models",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="user",
    )


def downgrade() -> None:
    # rollback 시 created_at만 삭제
    op.drop_column(
        "practice_session_models",
        "created_at",
        schema="user",
    )