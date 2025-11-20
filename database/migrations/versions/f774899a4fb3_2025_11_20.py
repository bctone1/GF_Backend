"""2025-11-20

Revision ID: f774899a4fb3
Revises: ccd4f818823f
Create Date: 2025-11-20 11:05:14.581635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f774899a4fb3"
down_revision: Union[str, Sequence[str], None] = "ccd4f818823f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) phone_number를 먼저 nullable=True로 추가
    op.add_column(
        "partner_promotion_requests",
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        schema="supervisor",
    )

    # 2) 기존 row에 기본값 채우기
    #    - 예전에 meta에 phone_number를 넣었다면 그 값 사용
    #    - 아니면 빈 문자열로 채워서 NULL이 안 남게 처리
    op.execute(
        """
        UPDATE supervisor.partner_promotion_requests
        SET phone_number = COALESCE(meta->>'phone_number', '')
        WHERE phone_number IS NULL
        """
    )

    # 3) 이제 NOT NULL 제약으로 강화
    op.alter_column(
        "partner_promotion_requests",
        "phone_number",
        existing_type=sa.String(length=32),
        nullable=False,
        schema="supervisor",
    )

    # 4) 더 이상 안 쓰는 email / full_name 컬럼 제거
    op.drop_column("partner_promotion_requests", "email", schema="supervisor")
    op.drop_column("partner_promotion_requests", "full_name", schema="supervisor")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "partner_promotion_requests",
        sa.Column("full_name", sa.TEXT(), autoincrement=False, nullable=True),
        schema="supervisor",
    )
    op.add_column(
        "partner_promotion_requests",
        sa.Column("email", postgresql.CITEXT(), autoincrement=False, nullable=True),
        schema="supervisor",
    )
    op.drop_column("partner_promotion_requests", "phone_number", schema="supervisor")
