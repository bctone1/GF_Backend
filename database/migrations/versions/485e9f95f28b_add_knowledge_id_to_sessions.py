"""add knowledge_id to sessions

Revision ID: 485e9f95f28b
Revises: 1c4860186d08
Create Date: 2025-12-11 14:53:12.802474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "485e9f95f28b"
down_revision: Union[str, Sequence[str], None] = "1c4860186d08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) 컬럼 추가
    op.add_column(
        "practice_sessions",
        sa.Column("knowledge_id", sa.BigInteger(), nullable=True),
        schema="user",
    )

    # 2) 인덱스 추가
    op.create_index(
        "idx_practice_sessions_knowledge",
        "practice_sessions",
        ["knowledge_id"],
        schema="user",
    )

    # 3) FK 추가 (user.documents.knowledge_id 를 참조)
    op.create_foreign_key(
        "fk_practice_sessions_knowledge",
        "practice_sessions",
        "documents",
        ["knowledge_id"],
        ["knowledge_id"],
        source_schema="user",
        referent_schema="user",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1) FK 제거
    op.drop_constraint(
        "fk_practice_sessions_knowledge",
        "practice_sessions",
        schema="user",
        type_="foreignkey",
    )

    # 2) 인덱스 제거
    op.drop_index(
        "idx_practice_sessions_knowledge",
        table_name="practice_sessions",
        schema="user",
    )

    # 3) 컬럼 제거
    op.drop_column("practice_sessions", "knowledge_id", schema="user")
