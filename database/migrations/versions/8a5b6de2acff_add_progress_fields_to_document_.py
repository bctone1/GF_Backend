"""add progress fields to document_processing_jobs

Revision ID: 8a5b6de2acff
Revises: 5da7caf461ec
Create Date: 2025-12-05 15:25:34.845775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a5b6de2acff'
down_revision: Union[str, Sequence[str], None] = '5da7caf461ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # user.document_processing_jobs 에 컬럼 추가
    op.add_column(
        "document_processing_jobs",
        sa.Column("step", sa.Text(), nullable=True),
        schema="user",
    )
    op.add_column(
        "document_processing_jobs",
        sa.Column(
            "progress",
            sa.Integer(),
            nullable=False,
            server_default="0",  # 기존 row 채우기용
        ),
        schema="user",
    )
    op.add_column(
        "document_processing_jobs",
        sa.Column("error_message", sa.Text(), nullable=True),
        schema="user",
    )

    # 기존 row 다 0으로 들어간 후에는 server_default는 굳이 안 써도 되니까 제거
    op.alter_column(
        "document_processing_jobs",
        "progress",
        server_default=None,
        schema="user",
    )


def downgrade() -> None:
    op.drop_column("document_processing_jobs", "error_message", schema="user")
    op.drop_column("document_processing_jobs", "progress", schema="user")
    op.drop_column("document_processing_jobs", "step", schema="user")