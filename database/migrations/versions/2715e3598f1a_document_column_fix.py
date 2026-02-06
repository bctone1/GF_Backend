"""document_column_fix

Revision ID: 2715e3598f1a
Revises: 38629e464cb1
Create Date: 2026-02-06 15:01:04.667976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '2715e3598f1a'
down_revision: Union[str, Sequence[str], None] = '38629e464cb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop constraints and index related to session_id
    op.drop_index("idx_documents_session_id", table_name="documents", schema="user")
    op.execute(text(
        'ALTER TABLE "user".documents DROP CONSTRAINT IF EXISTS chk_documents_scope_session_consistency'
    ))
    op.drop_constraint("fk_documents_session_id", "documents", schema="user")

    # Drop session_id column only (scope is kept)
    op.drop_column("documents", "session_id", schema="user")


def downgrade() -> None:
    # Re-add session_id column (nullable)
    op.add_column(
        "documents",
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        schema="user",
    )

    # Re-add FK constraint
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

    # Re-add CHECK constraint for scope-session_id consistency
    op.create_check_constraint(
        "chk_documents_scope_session_consistency",
        "documents",
        "(scope = 'knowledge_base' AND session_id IS NULL) OR scope = 'session'",
        schema="user",
    )

    # Re-add index
    op.create_index(
        "idx_documents_session_id",
        "documents",
        ["session_id"],
        schema="user",
    )