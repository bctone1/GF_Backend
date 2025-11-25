"""add_column_is_partner

Revision ID: ea0f1a62093d
Revises: 1d6c29e3e938
Create Date: 2025-11-24 12:21:14.416510

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea0f1a62093d'
down_revision: Union[str, Sequence[str], None] = '1d6c29e3e938'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) user.users 에 is_partner 추가만 남기기
    op.add_column(
        'users',
        sa.Column(
            'is_partner',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
        schema='user',
    )

def downgrade() -> None:
    # org_id 관련 부분 삭제
    # op.alter_column(
    #     'courses',
    #     'org_id',
    #     existing_type=sa.BIGINT(),
    #     nullable=True,
    #     schema='partner',
    # )

    op.drop_column('users', 'is_partner', schema='user')
