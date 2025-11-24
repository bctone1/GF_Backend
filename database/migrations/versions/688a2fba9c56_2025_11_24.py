"""2025-11-24

Revision ID: 688a2fba9c56
Revises: 8436c9b3fe33
Create Date: 2025-11-24 10:32:47.660769

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "688a2fba9c56"
down_revision: Union[str, Sequence[str], None] = "8436c9b3fe33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1) 공용 스키마 생성
    op.execute('CREATE SCHEMA IF NOT EXISTS "common"')

    # ==============================
    # links.org_user_link → common.org_user_link
    # links.partner_org_link → common.partner_org_link
    # ==============================

    op.create_table(
        "org_user_link",
        sa.Column("link_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.Text(), server_default=sa.text("'manager'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner','admin','manager','member')",
            name=op.f("ck_org_user_link_chk_org_user_link_role"),
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive','suspended','draft')",
            name=op.f("ck_org_user_link_chk_org_user_link_status"),
        ),
        sa.CheckConstraint(
            "(left_at IS NULL) OR (left_at >= joined_at)",
            name=op.f("ck_org_user_link_chk_org_user_link_left_after_join"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["supervisor.organizations.organization_id"],
            name=op.f("fk_org_user_link_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.users.user_id"],
            name=op.f("fk_org_user_link_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("link_id", name=op.f("pk_org_user_link")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
        schema="common",
    )

    op.create_index(
        "idx_org_user_active",
        "org_user_link",
        ["organization_id", "user_id"],
        unique=False,
        schema="common",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_org_user_org",
        "org_user_link",
        ["organization_id"],
        unique=False,
        schema="common",
    )
    op.create_index(
        "idx_org_user_role",
        "org_user_link",
        ["role"],
        unique=False,
        schema="common",
    )
    op.create_index(
        "idx_org_user_status",
        "org_user_link",
        ["status"],
        unique=False,
        schema="common",
    )
    op.create_index(
        "idx_org_user_user",
        "org_user_link",
        ["user_id"],
        unique=False,
        schema="common",
    )

    op.create_table(
        "partner_org_link",
        sa.Column("link_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("partner_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive','suspended','draft')",
            name=op.f("ck_partner_org_link_chk_partner_org_link_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["supervisor.organizations.organization_id"],
            name=op.f("fk_partner_org_link_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partner.partners.id"],
            name=op.f("fk_partner_org_link_partner_id_partners"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("link_id", name=op.f("pk_partner_org_link")),
        sa.UniqueConstraint("organization_id", "partner_id", name="uq_partner_org"),
        schema="common",
    )

    op.create_index(
        "idx_partner_org_org",
        "partner_org_link",
        ["organization_id"],
        unique=False,
        schema="common",
    )
    op.create_index(
        "idx_partner_org_partner",
        "partner_org_link",
        ["partner_id"],
        unique=False,
        schema="common",
    )
    op.create_index(
        "uq_partner_org_primary_once",
        "partner_org_link",
        ["organization_id"],
        unique=True,
        schema="common",
        postgresql_where=sa.text("is_primary = true"),
    )

    # links 스키마의 기존 테이블/인덱스 제거
    op.drop_index(
        op.f("idx_org_user_active"),
        table_name="org_user_link",
        schema="links",
        postgresql_where="(status = 'active'::text)",
    )
    op.drop_index(
        op.f("idx_org_user_org"),
        table_name="org_user_link",
        schema="links",
    )
    op.drop_index(
        op.f("idx_org_user_role"),
        table_name="org_user_link",
        schema="links",
    )
    op.drop_index(
        op.f("idx_org_user_status"),
        table_name="org_user_link",
        schema="links",
    )
    op.drop_index(
        op.f("idx_org_user_user"),
        table_name="org_user_link",
        schema="links",
    )
    op.drop_table("org_user_link", schema="links")

    op.drop_index(
        op.f("idx_class_instructors_class"),
        table_name="class_instructors",
        schema="partner",
    )
    op.drop_index(
        op.f("idx_class_instructors_partner_user"),
        table_name="class_instructors",
        schema="partner",
    )
    op.drop_table("class_instructors", schema="partner")

    op.drop_index(
        op.f("idx_partner_org_org"),
        table_name="partner_org_link",
        schema="links",
    )
    op.drop_index(
        op.f("idx_partner_org_partner"),
        table_name="partner_org_link",
        schema="links",
    )
    op.drop_index(
        op.f("uq_partner_org_primary_once"),
        table_name="partner_org_link",
        schema="links",
        postgresql_where="(is_primary = true)",
    )
    op.drop_table("partner_org_link", schema="links")

    # ==============================
    # partner.classes: partner_id 추가, course nullable, FK/제약 변경
    # ==============================

    # 1) partner_id 컬럼을 NULL 허용으로 먼저 추가
    op.add_column(
        "classes",
        sa.Column("partner_id", sa.BigInteger(), nullable=True),
        schema="partner",
    )

    # 2) course_id 를 nullable 로 변경 (독립 class 허용)
    op.alter_column(
        "classes",
        "course_id",
        existing_type=sa.BIGINT(),
        nullable=True,
        schema="partner",
    )

    # 3) 기존 데이터 매핑: courses.partner_id → classes.partner_id
    op.execute(
        """
        UPDATE partner.classes AS c
        SET partner_id = co.partner_id
        FROM partner.courses AS co
        WHERE c.course_id = co.id
        """
    )

    # 4) 이제 partner_id NOT NULL 제약 적용
    op.alter_column(
        "classes",
        "partner_id",
        existing_type=sa.BigInteger(),
        nullable=False,
        schema="partner",
    )

    # 5) 나머지 인덱스/제약/외래키 재구성
    op.drop_constraint(
        op.f("uq_classes_course_section"),
        "classes",
        schema="partner",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_classes_course_section",
        "classes",
        ["course_id", "section_code"],
        schema="partner",
    )
    op.create_index(
        "idx_classes_partner_status",
        "classes",
        ["partner_id", "status"],
        unique=False,
        schema="partner",
    )
    op.drop_constraint(
        op.f("fk_classes_course_id_courses"),
        "classes",
        schema="partner",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_classes_course_id_courses"),
        "classes",
        "courses",
        ["course_id"],
        ["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_classes_partner_id_partners"),
        "classes",
        "partners",
        ["partner_id"],
        ["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )

    # ==============================
    # partner.courses: org_id 추가, partner_id 제거, FK/인덱스 변경
    # ==============================

    # 여기서는 일단 NULL 허용으로 추가해서 NotNullViolation 방지
    op.add_column(
        "courses",
        sa.Column("org_id", sa.BigInteger(), nullable=True),
        schema="partner",
    )

    op.drop_index(
        op.f("idx_courses_partner_status"),
        table_name="courses",
        schema="partner",
    )
    op.drop_constraint(
        op.f("uq_courses_partner_course_key"),
        "courses",
        schema="partner",
        type_="unique",
    )
    op.create_index(
        "idx_courses_org_status",
        "courses",
        ["org_id", "status"],
        unique=False,
        schema="partner",
    )
    op.create_unique_constraint(
        "uq_courses_org_course_key",
        "courses",
        ["org_id", "course_key"],
        schema="partner",
    )
    op.drop_constraint(
        op.f("fk_courses_partner_id_partners"),
        "courses",
        schema="partner",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_courses_org_id_organizations"),
        "courses",
        "organizations",
        ["org_id"],
        ["organization_id"],
        source_schema="partner",
        referent_schema="supervisor",
        ondelete="CASCADE",
    )
    op.drop_column("courses", "partner_id", schema="partner")

    # ==============================
    # org_llm_settings FK, partner_users role 기본값
    # ==============================

    op.drop_constraint(
        op.f("fk_org_llm_settings_updated_by_partner_users"),
        "org_llm_settings",
        schema="partner",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_org_llm_settings_updated_by_partners"),
        "org_llm_settings",
        "partners",
        ["updated_by"],
        ["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="SET NULL",
    )

    op.alter_column(
        "partner_users",
        "role",
        existing_type=sa.TEXT(),
        server_default=sa.text("'partner'"),
        existing_nullable=False,
        schema="partner",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # partner_users.role 기본값 롤백
    op.alter_column(
        "partner_users",
        "role",
        existing_type=sa.TEXT(),
        server_default=sa.text("'partner'::text"),
        existing_nullable=False,
        schema="partner",
    )

    # org_llm_settings FK 롤백
    op.drop_constraint(
        op.f("fk_org_llm_settings_updated_by_partners"),
        "org_llm_settings",
        schema="partner",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_org_llm_settings_updated_by_partner_users"),
        "org_llm_settings",
        "partner_users",
        ["updated_by"],
        ["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="SET NULL",
    )

    # partner.courses 롤백
    op.add_column(
        "courses",
        sa.Column("partner_id", sa.BIGINT(), autoincrement=False, nullable=False),
        schema="partner",
    )
    op.drop_constraint(
        op.f("fk_courses_org_id_organizations"),
        "courses",
        schema="partner",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_courses_partner_id_partners"),
        "courses",
        "partners",
        ["partner_id"],
        ["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "uq_courses_org_course_key",
        "courses",
        schema="partner",
        type_="unique",
    )
    op.drop_index("idx_courses_org_status", table_name="courses", schema="partner")
    op.create_unique_constraint(
        op.f("uq_courses_partner_course_key"),
        "courses",
        ["partner_id", "course_key"],
        schema="partner",
        postgresql_nulls_not_distinct=False,
    )
    op.create_index(
        op.f("idx_courses_partner_status"),
        "courses",
        ["partner_id", "status"],
        unique=False,
        schema="partner",
    )
    op.drop_column("courses", "org_id", schema="partner")

    # partner.classes 롤백
    op.drop_constraint(
        op.f("fk_classes_partner_id_partners"),
        "classes",
        schema="partner",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_classes_course_id_courses"),
        "classes",
        schema="partner",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_classes_course_id_courses"),
        "classes",
        "courses",
        ["course_id"],
        ["id"],
        source_schema="partner",
        referent_schema="partner",
        ondelete="CASCADE",
    )
    op.drop_index("idx_classes_partner_status", table_name="classes", schema="partner")
    op.drop_constraint(
        "uq_classes_course_section",
        "classes",
        schema="partner",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_classes_course_section"),
        "classes",
        ["course_id", "section_code"],
        schema="partner",
        postgresql_nulls_not_distinct=True,
    )
    op.alter_column(
        "classes",
        "course_id",
        existing_type=sa.BIGINT(),
        nullable=False,
        schema="partner",
    )
    op.drop_column("classes", "partner_id", schema="partner")

    # links.partner_org_link 복구
    op.create_table(
        "partner_org_link",
        sa.Column("link_id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BIGINT(), nullable=False),
        sa.Column("partner_id", sa.BIGINT(), nullable=False),
        sa.Column(
            "status",
            sa.TEXT(),
            server_default=sa.text("'active'::text"),
            nullable=False,
        ),
        sa.Column(
            "is_primary",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("notes", sa.TEXT(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status = ANY (ARRAY['active'::text, 'inactive'::text, 'suspended'::text, 'draft'::text])",
            name=op.f("ck_partner_org_link_chk_partner_org_link_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["supervisor.organizations.organization_id"],
            name=op.f("fk_partner_org_link_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partner.partners.id"],
            name=op.f("fk_partner_org_link_partner_id_partners"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("link_id", name=op.f("pk_partner_org_link")),
        sa.UniqueConstraint(
            "organization_id",
            "partner_id",
            name=op.f("uq_partner_org"),
            postgresql_nulls_not_distinct=False,
        ),
        schema="links",
    )
    op.create_index(
        op.f("uq_partner_org_primary_once"),
        "partner_org_link",
        ["organization_id"],
        unique=True,
        schema="links",
        postgresql_where="(is_primary = true)",
    )
    op.create_index(
        op.f("idx_partner_org_partner"),
        "partner_org_link",
        ["partner_id"],
        unique=False,
        schema="links",
    )
    op.create_index(
        op.f("idx_partner_org_org"),
        "partner_org_link",
        ["organization_id"],
        unique=False,
        schema="links",
    )

    # partner.class_instructors 복구
    op.create_table(
        "class_instructors",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("class_id", sa.BIGINT(), nullable=False),
        sa.Column("partner_user_id", sa.BIGINT(), nullable=False),
        sa.Column(
            "role",
            sa.TEXT(),
            server_default=sa.text("'assistant'::text"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role = ANY (ARRAY['lead'::text, 'assistant'::text])",
            name=op.f("ck_class_instructors_chk_class_instructors_role"),
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["partner.classes.id"],
            name=op.f("fk_class_instructors_class_id_classes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["partner_user_id"],
            ["partner.partner_users.id"],
            name=op.f("fk_class_instructors_partner_user_id_partner_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_instructors")),
        sa.UniqueConstraint(
            "class_id",
            "partner_user_id",
            name=op.f("uq_class_instructors_unique"),
            postgresql_nulls_not_distinct=False,
        ),
        schema="partner",
    )
    op.create_index(
        op.f("idx_class_instructors_partner_user"),
        "class_instructors",
        ["partner_user_id"],
        unique=False,
        schema="partner",
    )
    op.create_index(
        op.f("idx_class_instructors_class"),
        "class_instructors",
        ["class_id"],
        unique=False,
        schema="partner",
    )

    # links.org_user_link 복구
    op.create_table(
        "org_user_link",
        sa.Column("link_id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BIGINT(), nullable=False),
        sa.Column("user_id", sa.BIGINT(), nullable=False),
        sa.Column(
            "role",
            sa.TEXT(),
            server_default=sa.text("'member'::text"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.TEXT(),
            server_default=sa.text("'active'::text"),
            nullable=False,
        ),
        sa.Column("notes", sa.TEXT(), nullable=True),
        sa.Column(
            "joined_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("left_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role = ANY (ARRAY['owner'::text, 'admin'::text, 'manager'::text, 'member'::text, 'student'::text, 'instructor'::text])",
            name=op.f("ck_org_user_link_chk_org_user_link_role"),
        ),
        sa.CheckConstraint(
            "status = ANY (ARRAY['active'::text, 'inactive'::text, 'suspended'::text, 'draft'::text])",
            name=op.f("ck_org_user_link_chk_org_user_link_status"),
        ),
        sa.CheckConstraint(
            "left_at IS NULL OR left_at >= joined_at",
            name=op.f("ck_org_user_link_chk_org_user_link_left_after_join"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["supervisor.organizations.organization_id"],
            name=op.f("fk_org_user_link_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.users.user_id"],
            name=op.f("fk_org_user_link_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("link_id", name=op.f("pk_org_user_link")),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name=op.f("uq_org_user"),
            postgresql_nulls_not_distinct=False,
        ),
        schema="links",
    )
    op.create_index(
        op.f("idx_org_user_user"),
        "org_user_link",
        ["user_id"],
        unique=False,
        schema="links",
    )
    op.create_index(
        op.f("idx_org_user_status"),
        "org_user_link",
        ["status"],
        unique=False,
        schema="links",
    )
    op.create_index(
        op.f("idx_org_user_role"),
        "org_user_link",
        ["role"],
        unique=False,
        schema="links",
    )
    op.create_index(
        op.f("idx_org_user_org"),
        "org_user_link",
        ["organization_id"],
        unique=False,
        schema="links",
    )
    op.create_index(
        op.f("idx_org_user_active"),
        "org_user_link",
        ["organization_id", "user_id"],
        unique=False,
        schema="links",
        postgresql_where="(status = 'active'::text)",
    )

    # 마지막으로 common 쪽 테이블/인덱스 제거
    op.drop_index(
        "uq_partner_org_primary_once",
        table_name="partner_org_link",
        schema="common",
        postgresql_where=sa.text("is_primary = true"),
    )
    op.drop_index("idx_partner_org_partner", table_name="partner_org_link", schema="common")
    op.drop_index("idx_partner_org_org", table_name="partner_org_link", schema="common")
    op.drop_table("partner_org_link", schema="common")

    op.drop_index("idx_org_user_user", table_name="org_user_link", schema="common")
    op.drop_index("idx_org_user_status", table_name="org_user_link", schema="common")
    op.drop_index("idx_org_user_role", table_name="org_user_link", schema="common")
    op.drop_index("idx_org_user_org", table_name="org_user_link", schema="common")
    op.drop_index(
        "idx_org_user_active",
        table_name="org_user_link",
        schema="common",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_table("org_user_link", schema="common")
