"""add llm columns to partner.courses

Revision ID: dd0ac8fed763
Revises: 78f40f015e59
Create Date: 2025-11-26 12:07:52.836101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dd0ac8fed763'
down_revision: Union[str, Sequence[str], None] = '78f40f015e59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # partner.courses 에 LLM 컬럼 2개 추가
    op.add_column(
        "courses",
        sa.Column("primary_model_id", sa.BigInteger(), nullable=True),
        schema="partner",
    )
    op.add_column(
        "courses",
        sa.Column(
            "allowed_model_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="partner",
    )

    # 필요하면 FK + 인덱스도 같이 (model_catalog 를 쓰고 있다면)
    op.create_foreign_key(
        "fk_courses_primary_model",
        "courses",
        "model_catalog",
        ["primary_model_id"],
        ["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # FK 만들었다면 먼저 삭제
    op.drop_constraint(
        "fk_courses_primary_model",
        "courses",
        schema="partner",
        type_="foreignkey",
    )

    op.drop_column("courses", "allowed_model_ids", schema="partner")
    op.drop_column("courses", "primary_model_id", schema="partner")