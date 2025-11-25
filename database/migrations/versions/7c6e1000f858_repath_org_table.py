"""repath_org_table

Revision ID: 7c6e1000f858
Revises: 32847829b9f1
Create Date: 2025-11-25 13:45:22.249530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c6e1000f858'
down_revision: Union[str, Sequence[str], None] = '32847829b9f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



from alembic import op

def upgrade() -> None:
    # 1) 기존 FK 제거
    op.drop_constraint(
        "fk_courses_org_id_organizations",
        "courses",
        schema="partner",
        type_="foreignkey",
    )

    # 2) partner.org(id) 로 새 FK 생성
    op.create_foreign_key(
        "fk_courses_org_id_partner_org",
        source_table="courses",
        referent_table="org",
        local_cols=["org_id"],
        remote_cols=["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )

def downgrade() -> None:
    op.drop_constraint(
        "fk_courses_org_id_partner_org",
        "courses",
        schema="partner",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_courses_org_id_organizations",
        "courses",
        "organizations",
        ["org_id"],
        ["organization_id"],
        source_schema="partner",
        referent_schema="supervisor",  # 예전 스키마에 맞게
    )
