"""Supervisor_table

Revision ID: 94a2f6a6374c
Revises: 412b8619c232
Create Date: 2025-11-11 11:59:04.674652
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "94a2f6a6374c"
down_revision: Union[str, Sequence[str], None] = "412b8619c232"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 테이블 리네임 (FK들은 자동으로 따라온다)
    op.rename_table("users", "supervisors", schema="supervisor")

    # 2) 인덱스/제약 이름 정리(선택적이지만 권장)
    op.execute('ALTER INDEX IF EXISTS "supervisor".ix_users_org_id RENAME TO ix_supervisors_org_id')
    op.execute('ALTER INDEX IF EXISTS "supervisor".ix_users_status RENAME TO ix_supervisors_status')
    op.execute('ALTER INDEX IF EXISTS "supervisor".ix_users_signup_at RENAME TO ix_supervisors_signup_at')
    op.execute('ALTER TABLE "supervisor".supervisors RENAME CONSTRAINT uq_users_email TO uq_supervisors_email')

    # 3) 과거에 잘못 붙은 FK 교정: partner.partner_users.user_id → user.users.user_id
    #    (이미 올바르면 DROP이 실패할 수 있으니 IF EXISTS 패턴 사용 불가 -> 실패하면 수동 제거 필요)
    try:
        op.drop_constraint("fk_partner_users_user_id_users", "partner_users", schema="partner", type_="foreignkey")
    except Exception:
        pass
    op.create_foreign_key(
        "fk_partner_users_user_id_users",
        "partner_users",
        "users",
        ["user_id"],
        ["user_id"],
        source_schema="partner",
        referent_schema="user",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # partner FK를 이전 상태(잘못된 supervisor.users)로 되돌림
    try:
        op.drop_constraint("fk_partner_users_user_id_users", "partner_users", schema="partner", type_="foreignkey")
    except Exception:
        pass
    op.create_foreign_key(
        "fk_partner_users_user_id_users",
        "partner_users",
        "users",
        ["user_id"],
        ["user_id"],
        source_schema="partner",
        referent_schema="supervisor",
        ondelete="SET NULL",
    )

    # 인덱스/제약 이름 롤백
    op.execute('ALTER TABLE "supervisor".supervisors RENAME CONSTRAINT uq_supervisors_email TO uq_users_email')
    op.execute('ALTER INDEX IF EXISTS "supervisor".ix_supervisors_org_id RENAME TO ix_users_org_id')
    op.execute('ALTER INDEX IF EXISTS "supervisor".ix_supervisors_status RENAME TO ix_users_status')
    op.execute('ALTER INDEX IF EXISTS "supervisor".ix_supervisors_signup_at RENAME TO ix_users_signup_at')

    # 테이블명 롤백
    op.rename_table("supervisors", "users", schema="supervisor")
