"""add generation_params to practice_session_models

Revision ID: 1c4860186d08
Revises: 55f4ed995db2
Create Date: 2025-12-10 11:06:45.535993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1c4860186d08'
down_revision: Union[str, Sequence[str], None] = '55f4ed995db2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "practice_session_models",
        sa.Column(
            "generation_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="user",
    )

    # 필요하면 여기서 기존 데이터에 기본값 세팅용 UPDATE 쿼리도 넣을 수 있음
    # 예: 전부 normal 프리셋으로 초기화하고 싶다면:
    # op.execute(
    #     """
    #     UPDATE "user".practice_session_models
    #     SET generation_params = jsonb_build_object(
    #         'temperature', 0.7,
    #         'top_p', 0.9,
    #         'response_length_preset', 'normal',
    #         'max_tokens', 512
    #     )
    #     WHERE generation_params = '{}'::jsonb
    #     """
    # )


def downgrade() -> None:
    op.drop_column(
        "practice_session_models",
        "generation_params",
        schema="user",
    )