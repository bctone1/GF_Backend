"""unify_partner_id_and_rename_partner_table

Revision ID: 9dcb16d63d1b
Revises: 692964f887b0
Create Date: 2025-11-27 10:40:31.898583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dcb16d63d1b'
down_revision: Union[str, Sequence[str], None] = '692964f887b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade() -> None:
    # 1) partner.partner  →  partner.partners 로 테이블 이름 변경
    op.rename_table("partner", "partners", schema="partner")

    # 2) user.users 에 partner_id 컬럼 추가
    op.add_column(
        "users",
        sa.Column("partner_id", sa.BigInteger(), nullable=True),
        schema="user",
    )

    # 3) FK: user.users.partner_id → partner.partners.id
    op.create_foreign_key(
        "fk_users_partner_id",
        "users",         # source table
        "partners",      # target table
        ["partner_id"],  # local cols
        ["id"],          # remote cols
        source_schema="user",
        referent_schema="partner",
        ondelete="SET NULL",
    )

    # 4) 기존 매핑: partners.user_id 기준으로 users.partner_id 채우기
    op.execute(
        """
        UPDATE "user"."users" AS u
        SET partner_id = p.id
        FROM "partner"."partners" AS p
        WHERE p.user_id = u.user_id
          AND u.partner_id IS NULL
        """
    )

    # 5) 예전 인덱스/컬럼 정리: is_partner → partner_id
    op.drop_index(
        "idx_users_is_partner_created",
        table_name="users",
        schema="user",
    )
    op.drop_column("users", "is_partner", schema="user")

    op.create_index(
        "idx_users_partner_created",
        "users",
        ["partner_id", "created_at"],
        schema="user",
    )


def downgrade() -> None:
    # 1) user.users 되돌리기
    op.drop_index(
        "idx_users_partner_created",
        table_name="users",
        schema="user",
    )

    # is_partner 복원
    op.add_column(
        "users",
        sa.Column(
            "is_partner",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="user",
    )

    # partner_id 있던 유저는 is_partner = true 로 마이그레이션
    op.execute(
        """
        UPDATE "user"."users"
        SET is_partner = TRUE
        WHERE partner_id IS NOT NULL
        """
    )

    # FK/partner_id 제거
    op.drop_constraint(
        "fk_users_partner_id",
        "users",
        schema="user",
        type_="foreignkey",
    )
    op.drop_column("users", "partner_id", schema="user")

    # 예전 인덱스 복원
    op.create_index(
        "idx_users_is_partner_created",
        "users",
        ["is_partner", "created_at"],
        schema="user",
    )

    # 2) partner.partners → partner.partner 이름 되돌리기
    op.rename_table("partners", "partner", schema="partner")
    op.create_foreign_key(
        "fk_users_partner_id",
        "users",         # source table
        "partners",      # target table
        ["partner_id"],  # local cols
        ["id"],          # remote cols
        source_schema="user",
        referent_schema="partner",
        ondelete="SET NULL",
    )

    # 기존 파트너 데이터 있으면 users.partner_id 채워넣기
    op.execute(
        """
        UPDATE "user"."users" AS u
        SET partner_id = p.id
        FROM "partner"."partners" AS p
        WHERE p.user_id = u.user_id
          AND u.partner_id IS NULL
        """
    )

    # 예전 인덱스/컬럼 제거
    op.drop_index(
        "idx_users_is_partner_created",
        table_name="users",
        schema="user",
    )
    op.drop_column("users", "is_partner", schema="user")

    # 새 인덱스 생성
    op.create_index(
        "idx_users_partner_created",
        "users",
        ["partner_id", "created_at"],
        schema="user",
    )


def downgrade() -> None:
    # ============================================
    # 1) user.users 되돌리기
    #    - idx_users_partner_created 제거
    #    - is_partner 복원 (+ 값 채우기)
    #    - FK/partner_id 제거
    # ============================================
    op.drop_index(
        "idx_users_partner_created",
        table_name="users",
        schema="user",
    )

    # is_partner 컬럼 복원 (기본 false)
    op.add_column(
        "users",
        sa.Column(
            "is_partner",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="user",
    )

    # partner_id 있던 유저는 is_partner = true 로 마이그레이션
    op.execute(
        """
        UPDATE "user"."users"
        SET is_partner = TRUE
        WHERE partner_id IS NOT NULL
        """
    )

    # FK/컬럼 제거
    op.drop_constraint(
        "fk_users_partner_id",
        "users",
        schema="user",
        type_="foreignkey",
    )
    op.drop_column("users", "partner_id", schema="user")

    # 옛 인덱스 복원
    op.create_index(
        "idx_users_is_partner_created",
        "users",
        ["is_partner", "created_at"],
        schema="user",
    )

    # ============================================
    # 2) partner.partners → partner.partner 되돌리기
    #    제약/인덱스 원복
    # ============================================
    # 새 인덱스/체크/유니크 제거
    op.drop_index("idx_partners_email", table_name="partners", schema="partner")
    op.drop_index("idx_partners_active", table_name="partners", schema="partner")
    op.drop_index("idx_partners_role", table_name="partners", schema="partner")
    op.drop_index("idx_partners_last_login", table_name="partners", schema="partner")

    op.drop_constraint(
        "chk_partners_role",
        "partners",
        schema="partner",
        type_="check",
    )
    op.drop_constraint(
        "uq_partners_user_id",
        "partners",
        schema="partner",
        type_="unique",
    )
    op.drop_constraint(
        "uq_partners_org_email",
        "partners",
        schema="partner",
        type_="unique",
    )

    # 옛 제약/인덱스 복원
    op.create_unique_constraint(
        "uq_partner_user_user",
        "partners",
        ["org_id", "user_id"],
        schema="partner",
    )
    op.create_unique_constraint(
        "uq_partner_user_email",
        "partners",
        ["org_id", "email"],
        schema="partner",
    )
    op.create_check_constraint(
        "chk_partner_role",
        "partners",
        "role IN ('partner','assistant')",
        schema="partner",
    )

    op.create_index(
        "idx_partner_email",
        "partners",
        ["org_id", "email"],
        schema="partner",
    )
    op.create_index(
        "idx_partner_active",
        "partners",
        ["is_active"],
        schema="partner",
    )
    op.create_index(
        "idx_partner_role",
        "partners",
        ["role"],
        schema="partner",
    )
    op.create_index(
        "idx_partner_last_login",
        "partners",
        ["last_login_at"],
        schema="partner",
    )

    # 마지막에 테이블 이름 되돌리기
    op.rename_table("partners", "partner", schema="partner")