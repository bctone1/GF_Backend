"""fix classes.partner_id foreign key

Revision ID: e13eb1fc9fd2
Revises: a7b6c7208470
Create Date: 2025-11-25 14:57:39.387074

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e13eb1fc9fd2'
down_revision: Union[str, Sequence[str], None] = 'a7b6c7208470'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # 1) 기존 FK 제거 (이름은 위에서 조회한 값으로 맞춰줄 것)
    op.drop_constraint(
        "fk_classes_partner_id_partners",  # 실제 이름과 맞게 수정
        "classes",
        schema="partner",
        type_="foreignkey",
    )

    # 2) 새 FK: partner.classes.partner_id -> partner.partner.id (PartnerUser)
    op.create_foreign_key(
        "fk_classes_partner_id_partner_users",
        "classes",          # source table
        "partner",          # referent table (PartnerUser.__tablename__)
        local_cols=["partner_id"],
        remote_cols=["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 롤백 시, 다시 org로 되돌리고 싶다면 아래처럼
    op.drop_constraint(
        "fk_classes_partner_id_partner_users",
        "classes",
        schema="partner",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_classes_partner_id_partners",
        "classes",
        "org",
        local_cols=["partner_id"],
        remote_cols=["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )
