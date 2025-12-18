"""delete_tag

Revision ID: 98fd45d5c846
Revises: 6ea1b86afaf9
Create Date: 2025-12-16 17:37:43.167734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98fd45d5c846'
down_revision: Union[str, Sequence[str], None] = '6ea1b86afaf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_table("document_tag_assignments", schema="user")
    op.drop_table("document_tags", schema="user")


def downgrade():
    op.create_table(
        "document_tags",
        op.Column("tag_id", op.BigInteger(), primary_key=True, autoincrement=True),
        op.Column("name", op.Text(), nullable=False, unique=True),
        schema="user",
    )
    op.create_index("idx_document_tags_name", "document_tags", ["name"], schema="user")

    op.create_table(
        "document_tag_assignments",
        op.Column("assignment_id", op.BigInteger(), primary_key=True, autoincrement=True),
        op.Column("knowledge_id", op.BigInteger(), nullable=False),
        op.Column("tag_id", op.BigInteger(), nullable=False),
        op.ForeignKeyConstraint(
            ["knowledge_id"], ["user.documents.knowledge_id"],
            ondelete="CASCADE",
        ),
        op.ForeignKeyConstraint(
            ["tag_id"], ["user.document_tags.tag_id"],
            ondelete="CASCADE",
        ),
        op.UniqueConstraint("knowledge_id", "tag_id", name="uq_document_tag_assignments_doc_tag"),
        schema="user",
    )
    op.create_index(
        "idx_document_tag_assignments_doc",
        "document_tag_assignments",
        ["knowledge_id"],
        schema="user",
    )
    op.create_index(
        "idx_document_tag_assignments_tag",
        "document_tag_assignments",
        ["tag_id"],
        schema="user",
    )