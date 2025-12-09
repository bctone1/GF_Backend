"""add fk practice_session_models.session_id -> practice_sessions

Revision ID: bb0e44533308
Revises: b824a41ec7fb
Create Date: 2025-12-09 11:43:26.649719

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb0e44533308'
down_revision: Union[str, Sequence[str], None] = 'b824a41ec7fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_practice_session_models_session_id",
        source_table="practice_session_models",
        referent_table="practice_sessions",
        local_cols=["session_id"],
        remote_cols=["session_id"],
        source_schema="user",
        referent_schema="user",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_practice_session_models_session_id",
        "practice_session_models",
        schema="user",
        type_="foreignkey",
    )