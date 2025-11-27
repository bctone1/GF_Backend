"""remove_enrollments_unused_one

Revision ID: 78f40f015e59
Revises: f029cb2a31af
Create Date: 2025-11-26 10:44:32.268216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78f40f015e59'
down_revision: Union[str, Sequence[str], None] = 'f029cb2a31af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # progress_percent / final_grade 제거
    with op.batch_alter_table("enrollments", schema="partner") as batch_op:
        batch_op.drop_column("progress_percent")
        batch_op.drop_column("final_grade")


def downgrade() -> None:
    # 롤백 시 복구
    with op.batch_alter_table("enrollments", schema="partner") as batch_op:
        batch_op.add_column(
            sa.Column(
                "progress_percent",
                sa.Numeric(5, 2),
                server_default=sa.text("0"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "final_grade",
                sa.Text,
                nullable=True,
            )
        )