"""add class_id to practice_sessions

Revision ID: <새 리비전 ID>
Revises: 22f0f6b321d8
Create Date: 2025-12-02 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "<새 리비전 ID>"
down_revision: Union[str, Sequence[str], None] = "22f0f6b321d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user.practice_sessions 에 class_id 컬럼 추가
    op.add_column(
        "practice_sessions",
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        schema="user",
    )

    # FK: user.practice_sessions.class_id → partner.classes.id (ON DELETE SET NULL)
    op.create_foreign_key(
        "fk_practice_sessions_class_id",
        "practice_sessions",          # source table
        "classes",                    # target table
        ["class_id"],                 # local cols
        ["id"],                       # remote cols
        source_schema="user",
        referent_schema="partner",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # FK 먼저 제거
    op.drop_constraint(
        "fk_practice_sessions_class_id",
        "practice_sessions",
        schema="user",
        type_="foreignkey",
    )

    # 컬럼 제거
    op.drop_column("practice_sessions", "class_id", schema="user")
