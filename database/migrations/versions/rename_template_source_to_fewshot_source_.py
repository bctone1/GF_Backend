"""rename_template_source_to_fewshot_source

Revision ID: rename_template_source_to_fewshot_source
Revises: fewshot_sharing
Create Date: 2026-02-02 16:27:39.494404
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision = "ren_tpl_to_fewshot_src"
down_revision = "fewshot_sharing"

CK_NAME = "ck_few_shot_examples_fewshot_source"
ALLOWED_SQL = "('user_fewshot','class_shared','partner_fewshot')"

# NULL 허용이면 아래처럼(권장) — nullable=True라서 NULL은 통과하도록 두는 게 맞음
NEW_CHECK = f"fewshot_source IS NULL OR fewshot_source IN {ALLOWED_SQL}"


def upgrade() -> None:
    # 1) 컬럼 rename
    op.alter_column(
        "few_shot_examples",
        "template_source",
        new_column_name="fewshot_source",
        schema="user",
        existing_type=sa.Text(),
        existing_nullable=True,
    )

    # 2) CHECK 추가 전에 기존 데이터 정리(허용값 밖이면 생성 시점에 바로 터짐)
    op.execute(
        f'''
        UPDATE "user".few_shot_examples
        SET fewshot_source = NULL
        WHERE fewshot_source IS NOT NULL
          AND fewshot_source NOT IN {ALLOWED_SQL}
        '''
    )

    # 3) CHECK 생성
    op.create_check_constraint(
        CK_NAME,
        "few_shot_examples",
        NEW_CHECK,
        schema="user",
    )


def downgrade() -> None:
    # 1) CHECK 제거
    op.drop_constraint(
        CK_NAME,
        "few_shot_examples",
        schema="user",
        type_="check",
    )

    # 2) 컬럼명 원복
    op.alter_column(
        "few_shot_examples",
        "fewshot_source",
        new_column_name="template_source",
        schema="user",
        existing_type=sa.Text(),
        existing_nullable=True,
    )