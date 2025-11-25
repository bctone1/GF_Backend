"""error fix

Revision ID: d1a4a1205053
Revises: e13eb1fc9fd2
Create Date: 2025-11-25 16:01:13.450128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1a4a1205053'
down_revision: Union[str, Sequence[str], None] = 'e13eb1fc9fd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# """Fix invite_codes.partner_id foreign key to partner.partner
#
# Revision ID: e13eb1fc9fd2
# Revises: <이전 리비전 ID로 교체>
# Create Date: 2025-11-25 15:30:00.000000
# """
# from typing import Sequence, Union
#
# from alembic import op
# import sqlalchemy as sa
#
#
# # revision identifiers, used by Alembic.
# revision: str = "e13eb1fc9fd2"
# down_revision: Union[str, Sequence[str], None] = "<이전 리비전 ID로 교체>"
# branch_labels: Union[str, Sequence[str], None] = None
# depends_on: Union[str, Sequence[str], None] = None
#

def upgrade() -> None:
    # partner.invite_codes.partner_id → FK 재생성
    # 기존: partner.org(id) 를 참조
    # 변경: partner.partner(id) 를 참조 (PartnerUser.id)
    op.drop_constraint(
        "fk_invite_codes_partner_id_partners",
        "invite_codes",
        schema="partner",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_invite_codes_partner_id_partners",
        source_table="invite_codes",
        referent_table="partner",
        local_cols=["partner_id"],
        remote_cols=["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 롤백 시 다시 org(id) 기준으로 되돌림
    op.drop_constraint(
        "fk_invite_codes_partner_id_partners",
        "invite_codes",
        schema="partner",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_invite_codes_partner_id_partners",
        source_table="invite_codes",
        referent_table="org",
        local_cols=["partner_id"],
        remote_cols=["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )
