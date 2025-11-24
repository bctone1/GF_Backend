"""partner_admin_to_partner

Revision ID: 1d6c29e3e938
Revises: 688a2fba9c56
Create Date: 2025-11-24 11:45:40.353948
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1d6c29e3e938'
down_revision: Union[str, Sequence[str], None] = '688a2fba9c56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1) 기존 체크 제약 먼저 삭제
    op.drop_constraint(
        "chk_partner_users_role",
        "partner_users",
        schema="partner",
        type_="check"
    )

    # 2) 그 다음 UPDATE
    op.execute("""
        UPDATE partner.partner_users
        SET role = 'partner'
        WHERE role NOT IN ('partner', 'assistant');
    """)

    # 3) 새로운 체크 제약 생성
    op.create_check_constraint(
        "chk_partner_users_role",
        "partner_users",
        "role IN ('partner','assistant')",
        schema="partner"
    )
    # 4) 승격 요청 기본값 수정
    op.alter_column(
        'partner_promotion_requests',
        'target_role',
        existing_type=sa.VARCHAR(length=64),
        server_default=sa.text("'partner'"),
        existing_nullable=False,
        schema='supervisor'
    )


def downgrade() -> None:

    # ===== 기본값 원복 =====
    op.alter_column(
        'partner_promotion_requests',
        'target_role',
        existing_type=sa.VARCHAR(length=64),
        server_default=sa.text("'partner_admin'::character varying"),
        existing_nullable=False,
        schema='supervisor'
    )

    # ===== role 체크 제약 원복 (partner_admin 로 되돌리기) =====
    op.drop_constraint(
        "chk_partner_users_role",
        "partner_users",
        schema="partner",
        type_="check"
    )

    op.create_check_constraint(
        "chk_partner_users_role",
        "partner_users",
        "role IN ('partner_admin')",
        schema="partner"
    )
