"""add_user_id_to_students

Revision ID: 70fe0bae721e
Revises: 68e9c6e196ed
Create Date: 2025-11-27 18:32:29.548135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70fe0bae721e'
down_revision: Union[str, Sequence[str], None] = '68e9c6e196ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # 1) 컬럼 추가
    op.add_column(
        "students",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        schema="partner",
    )

    # 2) FK 추가 (partner.students.user_id -> user.users.user_id)
    op.create_foreign_key(
        "fk_students_user_id_users",
        "students",
        "users",
        local_cols=["user_id"],
        remote_cols=["user_id"],
        source_schema="partner",
        referent_schema="user",
        ondelete="SET NULL",
    )

    # 3) 인덱스들
    op.create_index(
        "idx_students_user_id",
        "students",
        ["user_id"],
        schema="partner",
    )

    op.create_index(
        "uq_students_partner_user_notnull",
        "students",
        ["partner_id", "user_id"],
        unique=True,
        schema="partner",
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_students_partner_user_notnull", table_name="students", schema="partner")
    op.drop_index("idx_students_user_id", table_name="students", schema="partner")
    op.drop_constraint("fk_students_user_id_users", "students", schema="partner", type_="foreignkey")
    op.drop_column("students", "user_id", schema="partner")