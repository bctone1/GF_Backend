"""add practice_session_settings

Revision ID: a2e05c79600e
Revises: 485e9f95f28b
Create Date: 2025-12-15 13:37:14.345899

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2e05c79600e'
down_revision: Union[str, Sequence[str], None] = '485e9f95f28b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy.dialects import postgresql
    op.create_table(
        "practice_session_settings",
        sa.Column("setting_id", sa.BigInteger(), primary_key=True, autoincrement=True),

        sa.Column("session_id", sa.BigInteger(), nullable=False),

        sa.Column("style_preset", sa.Text(), nullable=True),

        sa.Column(
            "style_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "generation_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "few_shot_examples",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),

        sa.ForeignKeyConstraint(
            ["session_id"],
            ["user.practice_sessions.session_id"],
            ondelete="CASCADE",
            name="fk_practice_session_settings_session_id",
        ),
        sa.UniqueConstraint(
            "session_id",
            name="uq_practice_session_settings_session_id",
        ),
        schema="user",
    )

    op.create_index(
        "idx_practice_session_settings_session",
        "practice_session_settings",
        ["session_id"],
        unique=False,
        schema="user",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_practice_session_settings_session",
        table_name="practice_session_settings",
        schema="user",
    )
    op.drop_table("practice_session_settings", schema="user")