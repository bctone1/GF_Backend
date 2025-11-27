"""partner_students_drop_org_add_partner

Revision ID: 692964f887b0
Revises: dd0ac8fed763
Create Date: 2025-11-26 12:20:46.215439

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '692964f887b0'
down_revision: Union[str, Sequence[str], None] = 'dd0ac8fed763'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""partner_students_drop_org_add_partner

Revision ID: 692964f887b0
Revises: dd0ac8fed763
Create Date: 2025-11-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "692964f887b0"
down_revision = "dd0ac8fed763"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = "partner"

    # 0) 기존 FK 날리기 (이름은 실제 DB에서 확인한 값 사용)
    #    - org_id에 묶여 있든 partner_id에 묶여 있든 일단 제거
    op.drop_constraint(
        "fk_students_partner_id_partners",
        "students",
        schema=schema,
        type_="foreignkey",
    )

    # 1) 기존 org 기반 인덱스 제거
    #    (없으면 에러 날 수 있어서, 실제로 존재하는 이름만 사용)
    op.drop_index(
        "uq_students_org_email_notnull",
        table_name="students",
        schema=schema,
    )
    op.drop_index(
        "idx_students_org_email",
        table_name="students",
        schema=schema,
    )
    op.drop_index(
        "idx_students_org_status",
        table_name="students",
        schema=schema,
    )

    # 2) 컬럼 이름 변경: org_id  →  partner_id
    #    - 실제 데이터/NOT NULL 상태는 그대로 유지
    op.alter_column(
        "students",
        "org_id",
        new_column_name="partner_id",
        schema=schema,
    )

    # 3) partner 기준 인덱스 재생성
    op.create_index(
        "idx_students_partner_status",
        "students",
        ["partner_id", "status"],
        schema=schema,
    )
    op.create_index(
        "idx_students_partner_email",
        "students",
        ["partner_id", "email"],
        schema=schema,
    )
    op.create_index(
        "uq_students_partner_email_notnull",
        "students",
        ["partner_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
        schema=schema,
    )

    # 4) FK는 일단 생략
    #    - 지금 org_id 값이 partner_id로 유효하지 않을 수 있어서
    #    - 나중에 데이터 정리한 뒤 별도 마이그레이션에서 FK 추가하는게 안전함
    # 예시:
    # op.create_foreign_key(
    #     "fk_students_partner_id_partners",
    #     "students",
    #     "partners",
    #     ["partner_id"],
    #     ["id"],
    #     source_schema=schema,
    #     referent_schema=schema,
    #     ondelete="CASCADE",
    # )


def downgrade() -> None:
    schema = "partner"

    # 1) partner 기반 인덱스 제거
    op.drop_index(
        "uq_students_partner_email_notnull",
        table_name="students",
        schema=schema,
    )
    op.drop_index(
        "idx_students_partner_email",
        table_name="students",
        schema=schema,
    )
    op.drop_index(
        "idx_students_partner_status",
        table_name="students",
        schema=schema,
    )

    # 2) 컬럼 이름 복구: partner_id → org_id
    op.alter_column(
        "students",
        "partner_id",
        new_column_name="org_id",
        schema=schema,
    )

    # 3) org 기반 인덱스 복구
    op.create_index(
        "idx_students_org_status",
        "students",
        ["org_id", "status"],
        schema=schema,
    )
    op.create_index(
        "idx_students_org_email",
        "students",
        ["org_id", "email"],
        schema=schema,
    )
    op.create_index(
        "uq_students_org_email_notnull",
        "students",
        ["org_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
        schema=schema,
    )

    # 4) 예전 FK 복구 (정확한 대상은 기존 설계에 맞춰서 수정 가능)
    # op.create_foreign_key(
    #     "fk_students_partner_id_partners",
    #     "students",
    #     "org",
    #     ["org_id"],
    #     ["id"],
    #     source_schema=schema,
    #     referent_schema=schema,
    #     ondelete="CASCADE",
    # )
