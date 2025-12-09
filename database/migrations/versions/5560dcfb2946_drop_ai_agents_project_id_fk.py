"""drop ai_agents project_id fk

Revision ID: 5560dcfb2946
Revises: 9822317db03c
Create Date: 2025-12-08 17:43:43.643937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5560dcfb2946'
down_revision: Union[str, Sequence[str], None] = '9822317db03c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op


def upgrade():
    # 실제 DB에는 ai_agents.project_id FK가 없을 수 있으므로
    # 이 리비전은 스키마 변경 없이 넘긴다.
    pass


def downgrade():
    # 되돌릴 것도 없다.
    pass
