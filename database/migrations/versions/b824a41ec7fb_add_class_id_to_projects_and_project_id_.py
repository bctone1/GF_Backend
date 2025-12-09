"""add class_id to projects and project_id to practice_sessions

Revision ID: b824a41ec7fb
Revises: 5560dcfb2946
Create Date: 2025-12-09 10:49:00.555819

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b824a41ec7fb'
down_revision: Union[str, Sequence[str], None] = '5560dcfb2946'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --------------------------------------------------
    # 1) user.projects 에 class_id 추가
    # --------------------------------------------------
    op.add_column(
        "projects",
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        schema="user",
    )

    # owner_id + class_id 조합으로 조회 최적화 (내 클래스별 프로젝트 리스트용)
    op.create_index(
        "idx_projects_owner_class",
        "projects",
        ["owner_id", "class_id"],
        schema="user",
    )

    # FK: user.projects.class_id -> partner.classes.id
    op.create_foreign_key(
        "fk_projects_class_id_classes",
        source_table="projects",
        referent_table="classes",
        local_cols=["class_id"],
        remote_cols=["id"],
        source_schema="user",
        referent_schema="partner",
        ondelete="CASCADE",
    )

    # --------------------------------------------------
    # 2) user.practice_sessions 에 project_id 추가
    # --------------------------------------------------
    op.add_column(
        "practice_sessions",
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        schema="user",
    )

    op.create_index(
        "idx_practice_sessions_project",
        "practice_sessions",
        ["project_id"],
        schema="user",
    )

    # FK: user.practice_sessions.project_id -> user.projects.project_id
    op.create_foreign_key(
        "fk_practice_sessions_project_id_projects",
        source_table="practice_sessions",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["project_id"],
        source_schema="user",
        referent_schema="user",
        ondelete="SET NULL",
    )

    # --------------------------------------------------
    # (선택) 나중에 nullable=False 로 바꾸고 싶으면:
    #   1) 기존 row 들에 유효한 class_id / project_id 채우는 스크립트 먼저 돌리고
    #   2) 아래 alter_column 을 별도 리비전에서 실행하는 게 안전함.
    # --------------------------------------------------
    # op.alter_column(
    #     "projects",
    #     "class_id",
    #     existing_type=sa.BigInteger(),
    #     nullable=False,
    #     schema="user",
    # )
    # op.alter_column(
    #     "practice_sessions",
    #     "project_id",
    #     existing_type=sa.BigInteger(),
    #     nullable=False,
    #     schema="user",
    # )


def downgrade() -> None:
    # --------------------------------------------------
    # 2) practice_sessions 쪽부터 롤백
    # --------------------------------------------------
    op.drop_constraint(
        "fk_practice_sessions_project_id_projects",
        "practice_sessions",
        schema="user",
        type_="foreignkey",
    )
    op.drop_index(
        "idx_practice_sessions_project",
        table_name="practice_sessions",
        schema="user",
    )
    op.drop_column("practice_sessions", "project_id", schema="user")

    # --------------------------------------------------
    # 1) projects 쪽 롤백
    # --------------------------------------------------
    op.drop_constraint(
        "fk_projects_class_id_classes",
        "projects",
        schema="user",
        type_="foreignkey",
    )
    op.drop_index(
        "idx_projects_owner_class",
        table_name="projects",
        schema="user",
    )
    op.drop_column("projects", "class_id", schema="user")