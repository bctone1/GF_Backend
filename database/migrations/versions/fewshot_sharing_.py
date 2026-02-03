"""empty message

Revision ID: fewshot_sharing
Revises: e0377ccc47aa
Create Date: 2026-02-02 16:00:54.970070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fewshot_sharing'
down_revision: Union[str, Sequence[str], None] = 'e0377ccc47aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "few_shot_examples",
        sa.Column("template_source", sa.Text(), nullable=True),
        schema="user",
    )

    op.create_table(
        "few_shot_shares",
        sa.Column("share_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "example_id",
            sa.BigInteger(),
            sa.ForeignKey("user.few_shot_examples.example_id", ondelete="CASCADE"),
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
        sa.UniqueConstraint("example_id", "class_id", name="uq_few_shot_shares_example_class"),
        schema="user",
    )
    op.create_index(
        "idx_few_shot_shares_example",
        "few_shot_shares",
        ["example_id"],
        unique=False,
        schema="user",
    )
    op.create_index(
        "idx_few_shot_shares_class",
        "few_shot_shares",
        ["class_id"],
        unique=False,
        schema="user",
    )


def downgrade() -> None:
    op.drop_index("idx_few_shot_shares_class", table_name="few_shot_shares", schema="user")
    op.drop_index("idx_few_shot_shares_example", table_name="few_shot_shares", schema="user")
    op.drop_table("few_shot_shares", schema="user")

    op.drop_column("few_shot_examples", "template_source", schema="user")
