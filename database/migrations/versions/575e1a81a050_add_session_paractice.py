"""add session_paractice

Revision ID: 575e1a81a050
Revises: 3e2fcc72654c
Create Date: 2025-12-03 15:29:02.105247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '575e1a81a050'
down_revision: Union[str, Sequence[str], None] = '3e2fcc72654c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema = "user"

    # 1) 컬럼 추가 (일단 NULL 허용)
    op.add_column(
        "practice_responses",
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        schema=schema,
    )

    # 2) 기존 데이터 백필
    # practice_responses.session_model_id → practice_session_models.session_id 조인해서 채우기
    op.execute(
        """
        UPDATE "user".practice_responses r
        SET session_id = m.session_id
        FROM "user".practice_session_models m
        WHERE r.session_model_id = m.session_model_id
        """
    )

    # 3) NOT NULL로 변경
    op.alter_column(
        "practice_responses",
        "session_id",
        existing_type=sa.BigInteger(),
        nullable=False,
        schema=schema,
    )

    # 4) FK 추가 (sessions 삭제 시 응답도 같이 삭제)
    op.create_foreign_key(
        "fk_practice_responses_session_id_sessions",
        "practice_responses",
        "practice_sessions",
        local_cols=["session_id"],
        remote_cols=["session_id"],
        source_schema=schema,
        referent_schema=schema,
        ondelete="CASCADE",
    )

    # 5) 세션 기준 조회 인덱스 (세션 히스토리 조회용)
    op.create_index(
        "idx_practice_responses_session_time",
        "practice_responses",
        ["session_id", "created_at"],
        schema=schema,
    )


def downgrade() -> None:
    schema = "user"

    # 1) 인덱스 제거
    op.drop_index(
        "idx_practice_responses_session_time",
        table_name="practice_responses",
        schema=schema,
    )

    # 2) FK 제거
    op.drop_constraint(
        "fk_practice_responses_session_id_sessions",
        "practice_responses",
        type_="foreignkey",
        schema=schema,
    )

    # 3) 컬럼 제거
    op.drop_column(
        "practice_responses",
        "session_id",
        schema=schema,
    )