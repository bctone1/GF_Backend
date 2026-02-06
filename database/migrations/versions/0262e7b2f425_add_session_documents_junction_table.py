"""add session_documents junction table

Revision ID: 0262e7b2f425
Revises: af8a4f9def66
Create Date: 2026-02-06 10:36:18.560655

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0262e7b2f425'
down_revision: Union[str, Sequence[str], None] = 'af8a4f9def66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "session_documents",
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("knowledge_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("session_id", "knowledge_id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["user.practice_sessions.session_id"],
            name="fk_session_documents_session_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_id"],
            ["user.documents.knowledge_id"],
            name="fk_session_documents_knowledge_id",
            ondelete="CASCADE",
        ),
        schema="user",
    )

    op.create_index(
        "idx_session_documents_knowledge",
        "session_documents",
        ["knowledge_id"],
        schema="user",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_session_documents_knowledge",
        table_name="session_documents",
        schema="user",
    )
    op.drop_table("session_documents", schema="user")