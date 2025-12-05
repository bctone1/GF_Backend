"""add user.agent_shares table

Revision ID: 814a7649a69a
Revises: 575e1a81a050
Create Date: 2025-12-05 12:18:19.083851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '814a7649a69a'
down_revision: Union[str, Sequence[str], None] = '575e1a81a050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user.agent_shares 테이블 생성
    op.create_table(
        "agent_shares",
        sa.Column("share_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "agent_id",
            sa.BigInteger(),
            sa.ForeignKey("user.ai_agents.agent_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "class_id",
            sa.BigInteger(),
            sa.ForeignKey("partner.classes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shared_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user.users.user_id", ondelete="CASCADE"),
            nullable=False,
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
        sa.UniqueConstraint("agent_id", "class_id", name="uq_agent_shares_agent_class"),
        schema="user",
    )

    # 인덱스
    op.create_index(
        "idx_agent_shares_agent",
        "agent_shares",
        ["agent_id"],
        schema="user",
    )
    op.create_index(
        "idx_agent_shares_class",
        "agent_shares",
        ["class_id"],
        schema="user",
    )


def downgrade() -> None:
    # 인덱스 드랍
    op.drop_index(
        "idx_agent_shares_class",
        table_name="agent_shares",
        schema="user",
    )
    op.drop_index(
        "idx_agent_shares_agent",
        table_name="agent_shares",
        schema="user",
    )

    # 테이블 드랍
    op.drop_table("agent_shares", schema="user")
