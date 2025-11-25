"""Rename students.partner_id to org_id

Revision ID: f029cb2a31af
Revises: d1a4a1205053
Create Date: 2025-11-25 17:54:09.966068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f029cb2a31af'
down_revision: Union[str, Sequence[str], None] = 'd1a4a1205053'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 컬럼 이름 partner_id -> org_id
    op.alter_column(
        "students",
        "partner_id",
        new_column_name="org_id",
        schema="partner",
    )

    # 2) 인덱스 이름도 org 기준으로 맞추기 (실제 이름이 다르면 여기만 수정)
    op.execute(
        "ALTER INDEX IF EXISTS partner.idx_students_partner_status "
        "RENAME TO idx_students_org_status"
    )
    op.execute(
        "ALTER INDEX IF EXISTS partner.idx_students_partner_email "
        "RENAME TO idx_students_org_email"
    )
    op.execute(
        "ALTER INDEX IF EXISTS partner.uq_students_partner_email_notnull "
        "RENAME TO uq_students_org_email_notnull"
    )


def downgrade() -> None:
    # 되돌릴 때 org_id -> partner_id
    op.alter_column(
        "students",
        "org_id",
        new_column_name="partner_id",
        schema="partner",
    )

    op.execute(
        "ALTER INDEX IF EXISTS partner.idx_students_org_status "
        "RENAME TO idx_students_partner_status"
    )
    op.execute(
        "ALTER INDEX IF EXISTS partner.idx_students_org_email "
        "RENAME TO idx_students_partner_email"
    )
    op.execute(
        "ALTER INDEX IF EXISTS partner.uq_students_org_email_notnull "
        "RENAME TO uq_students_partner_email_notnull"
    )