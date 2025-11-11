"""code_to_course

Revision ID: 9817b5a1033a
Revises: 346d6ea365ba
Create Date: 2025-11-11 17:38:20.661084
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '9817b5a1033a'
down_revision: Union[str, Sequence[str], None] = '346d6ea365ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely (code → course_key)."""
    # 1️⃣ 새 컬럼 추가
    op.add_column('courses', sa.Column('course_key', sa.Text(), nullable=True), schema='partner')

    # 2️⃣ 기존 code 데이터를 복사
    op.execute("""
        UPDATE partner.courses
        SET course_key = COALESCE(code, UPPER(REGEXP_REPLACE(title, '\\W+', '', 'g')))
    """)

    # 3️⃣ 제약조건 교체
    op.drop_constraint('uq_courses_partner_code', 'courses', schema='partner', type_='unique')
    op.drop_column('courses', 'code', schema='partner')
    op.create_unique_constraint(
        'uq_courses_partner_course_key',
        'courses',
        ['partner_id', 'course_key'],
        schema='partner',
    )

    # 4️⃣ NULL 처리 후 NOT NULL 변경 (❗ schema 지정 필수)
    op.execute("""
        UPDATE partner.courses
        SET course_key = 'COURSE_' || id
        WHERE course_key IS NULL;
    """)
    op.alter_column('courses', 'course_key', nullable=False, schema='partner')  # ✅ 수정된 부분


def downgrade() -> None:
    """Downgrade schema (course_key → code)."""
    op.add_column('courses', sa.Column('code', sa.Text(), nullable=True), schema='partner')
    op.execute("UPDATE partner.courses SET code = course_key")
    op.drop_constraint('uq_courses_partner_course_key', 'courses', schema='partner', type_='unique')
    op.create_unique_constraint('uq_courses_partner_code', 'courses', ['partner_id', 'code'], schema='partner')
    op.alter_column('courses', 'code', nullable=False, schema='partner')
    op.drop_column('courses', 'course_key', schema='partner')
