"""add few_shot_example_id to practice_session_settings

Revision ID: 3b0b0b3d4b7d
Revises: 108114628b3f
Create Date: 2026-01-09 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3b0b0b3d4b7d"
down_revision: Union[str, Sequence[str], None] = "108114628b3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "practice_session_settings",
        sa.Column("few_shot_example_id", sa.BigInteger(), nullable=True),
        schema="user",
    )
    op.create_foreign_key(
        "fk_practice_session_settings_few_shot_example_id",
        "practice_session_settings",
        "few_shot_examples",
        ["few_shot_example_id"],
        ["example_id"],
        source_schema="user",
        referent_schema="user",
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_practice_session_settings_few_shot_example",
        "practice_session_settings",
        ["few_shot_example_id"],
        schema="user",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_practice_session_settings_few_shot_example",
        table_name="practice_session_settings",
        schema="user",
    )
    op.drop_constraint(
        "fk_practice_session_settings_few_shot_example_id",
        "practice_session_settings",
        schema="user",
        type_="foreignkey",
    )
    op.drop_column("practice_session_settings", "few_shot_example_id", schema="user")