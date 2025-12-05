"""not_course_model_but_class_model

Revision ID: 5eb24ecbb1e6
Revises: 70fe0bae721e
Create Date: 2025-12-02 15:22:38.949366

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5eb24ecbb1e6'
down_revision: Union[str, Sequence[str], None] = '70fe0bae721e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1) classes 테이블에 LLM 관련 컬럼 추가
    op.add_column(
        'classes',
        sa.Column('primary_model_id', sa.BigInteger(), nullable=True),
        schema='partner',
    )
    op.add_column(
        'classes',
        sa.Column(
            'allowed_model_ids',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema='partner',
    )

    # 서버 기본값은 데이터 채운 뒤 제거 (원하면 유지해도 무방)
    op.alter_column(
        'classes',
        'allowed_model_ids',
        server_default=None,
        schema='partner',
    )

    # 2) FK & 인덱스 생성 (classes.primary_model_id → model_catalog.id)
    op.create_foreign_key(
        'fk_classes_primary_model_id_model_catalog',
        'classes',
        'model_catalog',
        ['primary_model_id'],
        ['id'],
        source_schema='partner',
        referent_schema='partner',
        ondelete='SET NULL',
    )

    op.create_index(
        'idx_classes_primary_model',
        'classes',
        ['primary_model_id'],
        schema='partner',
    )

    # 3) 기존 courses 에 있던 설정을 classes 로 복사
    #    - course 에 primary_model_id / allowed_model_ids 가 설정되어 있으면
    #      해당 course 에 소속된 class 들에 동일하게 복사
    op.execute(
        """
        UPDATE partner.classes AS cls
        SET
            primary_model_id = crs.primary_model_id,
            allowed_model_ids = COALESCE(crs.allowed_model_ids, '[]'::jsonb)
        FROM partner.courses AS crs
        WHERE cls.course_id = crs.id
        """
    )

    # 4) courses 테이블에서 LLM 관련 컬럼 제거
    #    (FK 는 컬럼 드롭 시 자동으로 제거됨)
    with op.batch_alter_table('courses', schema='partner') as batch_op:
        batch_op.drop_column('primary_model_id')
        batch_op.drop_column('allowed_model_ids')


def downgrade() -> None:
    """Downgrade schema."""

    # 1) courses 테이블에 LLM 컬럼 복구
    op.add_column(
        'courses',
        sa.Column('primary_model_id', sa.BigInteger(), nullable=True),
        schema='partner',
    )
    op.add_column(
        'courses',
        sa.Column(
            'allowed_model_ids',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema='partner',
    )
    op.alter_column(
        'courses',
        'allowed_model_ids',
        server_default=None,
        schema='partner',
    )

    # FK 복구 (courses.primary_model_id → model_catalog.id)
    op.create_foreign_key(
        'fk_courses_primary_model_id_model_catalog',
        'courses',
        'model_catalog',
        ['primary_model_id'],
        ['id'],
        source_schema='partner',
        referent_schema='partner',
        ondelete='SET NULL',
    )

    # 데이터 역방향 마이그레이션
    # 여러 class 가 서로 다른 설정을 가질 수 있으므로,
    # 여기서는 안전하게 NULL / 빈 배열로 두거나, 하나만 선택하는 방식 등
    # 정책이 필요하다. 일단 손실 없이 구조만 되돌리는 정도로 두고,
    # 필요시 수동으로 채워넣는 것을 권장.
    op.execute(
        """
        UPDATE partner.courses
        SET
            primary_model_id = NULL,
            allowed_model_ids = '[]'::jsonb
        """
    )

    # 2) classes 의 FK/인덱스 및 컬럼 제거
    op.drop_index(
        'idx_classes_primary_model',
        table_name='classes',
        schema='partner',
    )
    op.drop_constraint(
        'fk_classes_primary_model_id_model_catalog',
        'classes',
        schema='partner',
        type_='foreignkey',
    )

    with op.batch_alter_table('classes', schema='partner') as batch_op:
        batch_op.drop_column('primary_model_id')
        batch_op.drop_column('allowed_model_ids')
