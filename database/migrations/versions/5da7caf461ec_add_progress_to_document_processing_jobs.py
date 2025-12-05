"""add progress to document_processing_jobs

Revision ID: 5da7caf461ec
Revises: 814a7649a69a
Create Date: 2025-12-05 13:39:27.697764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '5da7caf461ec'
down_revision: Union[str, Sequence[str], None] = '814a7649a69a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    def upgrade():
        op.add_column(
            "document_processing_jobs",
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            schema="user",
        )
        op.add_column(
            "document_processing_jobs",
            sa.Column("step", sa.Text(), nullable=True),
            schema="user",
        )
        op.add_column(
            "document_processing_jobs",
            sa.Column("error_message", sa.Text(), nullable=True),
            schema="user",
        )
        op.create_check_constraint(
            "chk_document_jobs_progress_range",
            "document_processing_jobs",
            "progress >= 0 AND progress <= 100",
            schema="user",
        )


def downgrade() -> None:
    """Downgrade schema."""
    pass
