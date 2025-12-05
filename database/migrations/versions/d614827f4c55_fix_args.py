"""fix args

Revision ID: d614827f4c55
Revises: 609db1bbf862
Create Date: 2025-12-03 11:46:14.063391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd614827f4c55'
down_revision: Union[str, Sequence[str], None] = '609db1bbf862'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) 기존 ongoing → active로 데이터 정리
    op.execute(
        "UPDATE partner.classes SET status = 'active' WHERE status = 'ongoing';"
    )

    # 2) 기존 체크 제약 삭제
    op.execute(
        "ALTER TABLE partner.classes DROP CONSTRAINT IF EXISTS chk_classes_status;"
    )

    # 3) 새로운 체크 제약 추가
    op.execute(
        "ALTER TABLE partner.classes "
        "ADD CONSTRAINT chk_classes_status "
        "CHECK (status IN ('planned','active','ended'));"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # rollback 시 active → ongoing 되돌리기
    op.execute(
        "UPDATE partner.classes SET status = 'ongoing' WHERE status = 'active';"
    )

    op.execute(
        "ALTER TABLE partner.classes DROP CONSTRAINT IF EXISTS chk_classes_status;"
    )

    op.execute(
        "ALTER TABLE partner.classes "
        "ADD CONSTRAINT chk_classes_status "
        "CHECK (status IN ('planned','ongoing','ended'));"
    )
