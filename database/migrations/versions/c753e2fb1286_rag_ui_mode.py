"""rag_ui_mode

Revision ID: c753e2fb1286
Revises: ren_tpl_to_fewshot_src
Create Date: 2026-02-04 10:34:20.070158

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c753e2fb1286'
down_revision: Union[str, Sequence[str], None] = 'ren_tpl_to_fewshot_src'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("rag_ui_mode", sa.Text(), nullable=True),
        schema="user",
    )
    op.create_check_constraint(
        "chk_documents_progress_range",
        "documents",
        "progress >= 0 AND progress <= 100",
        schema="user",
    )
    op.create_check_constraint(
        "chk_documents_rag_ui_mode_enum",
        "documents",
        "rag_ui_mode IS NULL OR rag_ui_mode IN ('simple', 'advanced', 'compare')",
        schema="user",
    )

    op.create_table(
        "practice_feature_stats",
        sa.Column("stat_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        sa.Column("feature_type", sa.Text(), nullable=False),
        sa.Column("usage_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("usage_count >= 0", name="chk_practice_feature_stats_count_nonneg"),
        sa.CheckConstraint(
            "feature_type IN ('parameter_tuned', 'fewshot_used', 'file_attached', 'kb_connected')",
            name="chk_practice_feature_stats_feature_type_enum",
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["partner.classes.id"],
            name="fk_practice_feature_stats_class_id_classes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.users.user_id"],
            name="fk_practice_feature_stats_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("stat_id", name="pk_practice_feature_stats"),
        sa.UniqueConstraint(
            "user_id",
            "class_id",
            "feature_type",
            name="uq_practice_feature_stats_user_class_feature",
        ),
        schema="user",
    )
    op.create_index(
        "idx_practice_feature_stats_user_class",
        "practice_feature_stats",
        ["user_id", "class_id"],
        unique=False,
        schema="user",
    )
    op.create_index(
        "idx_practice_feature_stats_feature_type",
        "practice_feature_stats",
        ["feature_type"],
        unique=False,
        schema="user",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_practice_feature_stats_feature_type",
        table_name="practice_feature_stats",
        schema="user",
    )
    op.drop_index(
        "idx_practice_feature_stats_user_class",
        table_name="practice_feature_stats",
        schema="user",
    )
    op.drop_table("practice_feature_stats", schema="user")

    op.drop_constraint(
        "chk_documents_rag_ui_mode_enum",
        "documents",
        schema="user",
        type_="check",
    )
    op.drop_constraint(
        "chk_documents_progress_range",
        "documents",
        schema="user",
        type_="check",
    )
    op.drop_column("documents", "rag_ui_mode", schema="user")