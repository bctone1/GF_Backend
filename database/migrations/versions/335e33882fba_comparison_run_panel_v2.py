"""comparison_run_panel_v2

Revision ID: 335e33882fba
Revises: 95e2356b06a6
Create Date: 2026-01-26 17:39:14.771581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '335e33882fba'
down_revision: Union[str, Sequence[str], None] = '95e2356b06a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 기존 index 제거
    op.drop_index(
        "idx_practice_comparison_runs_session_time",
        table_name="practice_comparison_runs",
        schema="user",
    )

    # 2) 기존 컬럼 제거 (A/B JSON 스냅샷 방식 폐기)
    op.drop_column("practice_comparison_runs", "panel_a_config", schema="user")
    op.drop_column("practice_comparison_runs", "panel_b_config", schema="user")

    # 3) 새 컬럼 추가
    # NOTE: 기존 row가 있을 수 있으니 NOT NULL 컬럼은 server_default로 임시 backfill 후 default 제거
    op.add_column(
        "practice_comparison_runs",
        sa.Column("panel", sa.String(length=1), nullable=False, server_default=sa.text("'a'")),
        schema="user",
    )
    op.add_column(
        "practice_comparison_runs",
        sa.Column("mode", sa.String(length=10), nullable=False, server_default=sa.text("'llm'")),
        schema="user",
    )
    op.add_column(
        "practice_comparison_runs",
        sa.Column("model_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema="user",
    )

    op.add_column(
        "practice_comparison_runs",
        sa.Column("knowledge_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="user",
    )
    op.add_column(
        "practice_comparison_runs",
        sa.Column("top_k", sa.Integer(), nullable=True),
        schema="user",
    )
    op.add_column(
        "practice_comparison_runs",
        sa.Column("chunk_size", sa.Integer(), nullable=True),
        schema="user",
    )
    op.add_column(
        "practice_comparison_runs",
        sa.Column("threshold", sa.Numeric(10, 6), nullable=True),
        schema="user",
    )

    # 4) 제약조건 추가
    op.create_check_constraint(
        "chk_practice_comparison_runs_panel",
        "practice_comparison_runs",
        "panel in ('a','b')",
        schema="user",
    )
    op.create_check_constraint(
        "chk_practice_comparison_runs_mode",
        "practice_comparison_runs",
        "mode in ('llm','doc','rag')",
        schema="user",
    )

    # 5) 새 index 생성
    op.create_index(
        "idx_practice_comparison_runs_session_panel_time",
        "practice_comparison_runs",
        ["session_id", "panel", "created_at"],
        unique=False,
        schema="user",
    )

    # 6) 임시 default 제거(앞으로는 API가 반드시 값을 주도록)
    op.alter_column("practice_comparison_runs", "panel", server_default=None, schema="user")
    op.alter_column("practice_comparison_runs", "mode", server_default=None, schema="user")
    op.alter_column("practice_comparison_runs", "model_names", server_default=None, schema="user")


def downgrade() -> None:
    # 1) 새 index 제거
    op.drop_index(
        "idx_practice_comparison_runs_session_panel_time",
        table_name="practice_comparison_runs",
        schema="user",
    )

    # 2) 새 제약 제거
    op.drop_constraint(
        "chk_practice_comparison_runs_panel",
        "practice_comparison_runs",
        type_="check",
        schema="user",
    )
    op.drop_constraint(
        "chk_practice_comparison_runs_mode",
        "practice_comparison_runs",
        type_="check",
        schema="user",
    )

    # 3) 새 컬럼 제거
    op.drop_column("practice_comparison_runs", "threshold", schema="user")
    op.drop_column("practice_comparison_runs", "chunk_size", schema="user")
    op.drop_column("practice_comparison_runs", "top_k", schema="user")
    op.drop_column("practice_comparison_runs", "knowledge_ids", schema="user")
    op.drop_column("practice_comparison_runs", "model_names", schema="user")
    op.drop_column("practice_comparison_runs", "mode", schema="user")
    op.drop_column("practice_comparison_runs", "panel", schema="user")

    # 4) 기존 컬럼 복구 (A/B JSON 스냅샷)
    op.add_column(
        "practice_comparison_runs",
        sa.Column("panel_a_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="user",
    )
    op.add_column(
        "practice_comparison_runs",
        sa.Column("panel_b_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="user",
    )

    # 5) 기존 index 복구
    op.create_index(
        "idx_practice_comparison_runs_session_time",
        "practice_comparison_runs",
        ["session_id", "created_at"],
        unique=False,
        schema="user",
    )