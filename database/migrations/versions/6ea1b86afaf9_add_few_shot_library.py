"""add_few_shot_library

Revision ID: 6ea1b86afaf9
Revises: a2e05c79600e
Create Date: 2025-12-16 13:08:51.681837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6ea1b86afaf9'
down_revision: Union[str, Sequence[str], None] = 'a2e05c79600e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 기존 settings의 JSONB few_shot_examples 컬럼 제거
    op.drop_column("practice_session_settings", "few_shot_examples", schema="user")

    # 2) (안 쓰는) rating / comparisons 테이블 제거 (있던 경우)
    op.drop_table("practice_ratings", schema="user")
    op.drop_table("model_comparisons", schema="user")

    # 3) 개인 few-shot 라이브러리 테이블 생성
    from sqlalchemy.dialects import postgresql
    op.create_table(
        "few_shot_examples",
        sa.Column("example_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user.users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        schema="user",
    )
    op.create_index(
        "idx_few_shot_examples_user",
        "few_shot_examples",
        ["user_id"],
        unique=False,
        schema="user",
    )

    # 4) settings ↔ example 매핑 테이블 생성
    op.create_table(
        "practice_session_setting_few_shots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "setting_id",
            sa.BigInteger(),
            sa.ForeignKey("user.practice_session_settings.setting_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "example_id",
            sa.BigInteger(),
            sa.ForeignKey("user.few_shot_examples.example_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("setting_id", "example_id", name="uq_setting_example"),
        schema="user",
    )
    op.create_index(
        "idx_setting_few_shots_setting",
        "practice_session_setting_few_shots",
        ["setting_id"],
        unique=False,
        schema="user",
    )
    op.create_index(
        "idx_setting_few_shots_example",
        "practice_session_setting_few_shots",
        ["example_id"],
        unique=False,
        schema="user",
    )


def downgrade() -> None:
    # 1) 매핑 테이블 제거
    op.drop_index("idx_setting_few_shots_example", table_name="practice_session_setting_few_shots", schema="user")
    op.drop_index("idx_setting_few_shots_setting", table_name="practice_session_setting_few_shots", schema="user")
    op.drop_table("practice_session_setting_few_shots", schema="user")

    # 2) 라이브러리 테이블 제거
    op.drop_index("idx_few_shot_examples_user", table_name="few_shot_examples", schema="user")
    op.drop_table("few_shot_examples", schema="user")

    # 3) settings에 JSONB few_shot_examples 컬럼 복구
    op.add_column(
        "practice_session_settings",
        sa.Column(
            "few_shot_examples",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema="user",
    )

    # 4) (구버전) rating / comparisons 테이블 복구
    op.create_table(
        "model_comparisons",
        sa.Column("comparison_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.BigInteger(),
            sa.ForeignKey("user.practice_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_a", sa.Text(), nullable=False),
        sa.Column("model_b", sa.Text(), nullable=False),
        sa.Column("winner_model", sa.Text(), nullable=True),
        sa.Column("latency_diff_ms", sa.Integer(), nullable=True),
        sa.Column("token_diff", sa.Integer(), nullable=True),
        sa.Column("user_feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="user",
    )

    op.create_table(
        "practice_ratings",
        sa.Column("rating_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "response_id",
            sa.BigInteger(),
            sa.ForeignKey("user.practice_responses.response_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user.users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="user",
    )