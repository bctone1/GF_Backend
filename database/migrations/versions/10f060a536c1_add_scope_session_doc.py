"""add scope_session_doc

Revision ID: 10f060a536c1
Revises: c753e2fb1286
Create Date: 2026-02-05 10:10:20.539002

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10f060a536c1'
down_revision: Union[str, Sequence[str], None] = 'c753e2fb1286'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # scope 컬럼 추가 (NOT NULL, default 'knowledge_base')
    op.add_column(
        "documents",
        sa.Column("scope", sa.Text(), nullable=False, server_default=sa.text("'knowledge_base'")),
        schema="user",
    )

    # session_id 컬럼 추가 (nullable, FK → user.practice_sessions)
    op.add_column(
        "documents",
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        schema="user",
    )

    # FK constraint
    op.create_foreign_key(
        "fk_documents_session_id",
        "documents",
        "practice_sessions",
        ["session_id"],
        ["session_id"],
        source_schema="user",
        referent_schema="user",
        ondelete="SET NULL",
    )

    # CHECK: scope enum
    op.create_check_constraint(
        "chk_documents_scope_enum",
        "documents",
        "scope IN ('knowledge_base', 'session')",
        schema="user",
    )

    # CHECK: scope-session_id 정합성
    op.create_check_constraint(
        "chk_documents_scope_session_consistency",
        "documents",
        "(scope = 'knowledge_base' AND session_id IS NULL) OR scope = 'session'",
        schema="user",
    )

    # Index on session_id
    op.create_index(
        "idx_documents_session_id",
        "documents",
        ["session_id"],
        schema="user",
    )


def downgrade() -> None:
    op.drop_index("idx_documents_session_id", table_name="documents", schema="user")
    op.drop_constraint("chk_documents_scope_session_consistency", "documents", schema="user")
    op.drop_constraint("chk_documents_scope_enum", "documents", schema="user")
    op.drop_constraint("fk_documents_session_id", "documents", schema="user")
    op.drop_column("documents", "session_id", schema="user")
    op.drop_column("documents", "scope", schema="user")
