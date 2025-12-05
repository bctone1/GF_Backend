"""add model_name_to_practice_responses

Revision ID: 3e2fcc72654c
Revises: e97684f62236
Create Date: 2025-12-03 14:54:27.912008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e2fcc72654c'
down_revision: Union[str, Sequence[str], None] = 'e97684f62236'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 컬럼 먼저 nullable=True 로 추가
    op.add_column(
        "practice_responses",
        sa.Column("model_name", sa.Text(), nullable=True),
        schema="user",  # ← 스키마 주의
    )

    # 2) 기존 데이터 백필 (session_model 에서 model_name 가져오기)
    op.execute(
        """
        UPDATE "user".practice_responses pr
        SET model_name = psm.model_name
        FROM "user".practice_session_models psm
        WHERE pr.session_model_id = psm.session_model_id
        """
    )

    # 3) 이제 NOT NULL 로 변경
    op.alter_column(
        "practice_responses",
        "model_name",
        schema="user",
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column(
        "practice_responses",
        "model_name",
        schema="user",
    )