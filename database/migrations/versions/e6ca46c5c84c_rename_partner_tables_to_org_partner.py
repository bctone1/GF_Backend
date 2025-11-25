"""rename partner tables to org/partner

Revision ID: e6ca46c5c84c
Revises: 9cce79e5687c
Create Date: 2025-11-24 17:05:38.477695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6ca46c5c84c'
down_revision: Union[str, Sequence[str], None] = '9cce79e5687c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 테이블 이름 변경
    op.execute('ALTER TABLE "partner"."partners" RENAME TO "org"')
    op.execute('ALTER TABLE "partner"."partner_users" RENAME TO "partner"')

    # 2) FK/인덱스/제약 이름까지 정리하고 싶으면 ALTER INDEX/CONSTRAINT 로 추가
    # (이 부분은 나중에 autogenerate diff 보고 정리해도 됨)


def downgrade() -> None:
    op.execute('ALTER TABLE "partner"."org" RENAME TO "partners"')
    op.execute('ALTER TABLE "partner"."partner" RENAME TO "partner_users"')
