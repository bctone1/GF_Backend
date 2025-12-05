"""change classes status to active

Revision ID: e97684f62236
Revises: d614827f4c55
Create Date: 2025-12-03 11:51:15.978824

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e97684f62236'
down_revision: Union[str, Sequence[str], None] = 'd614827f4c55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) 기존 데이터 정리: ongoing -> active
    op.execute(
        "UPDATE partner.classes SET status = 'active' WHERE status = 'ongoing';"
    )

    # 2) 기존 CHECK 제약 삭제
    #    여기 이름은 'ck_...' 이 아니라 'chk_classes_status' 로 넘겨야 함
    op.drop_constraint(
        "chk_classes_status",   # ★ 여기!
        "classes",
        schema="partner",
        type_="check",
    )

    # 3) 새 CHECK 제약 추가 (planned | active | ended)
    op.create_check_constraint(
        "chk_classes_status",   # constraint_name
        "classes",
        condition="status IN ('planned','active','ended')",
        schema="partner",
    )



def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "UPDATE partner.classes SET status = 'ongoing' WHERE status = 'active';"
    )

    op.drop_constraint(
        "ck_classes_chk_classes_status",
        "classes",
        schema="partner",
        type_="check",
    )

    op.create_check_constraint(
        "ck_classes_chk_classes_status",
        "classes",
        condition="status IN ('planned','ongoing','ended')",
        schema="partner",
    )