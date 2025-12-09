from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "2fd72a73adc7"
down_revision = "bb0e44533308"  # 너 프로젝트에서 이미 있는 값 그대로 두면 됨
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) status 컬럼 추가 (아직 없다고 가정)
    op.add_column(
        "practice_sessions",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=text("'active'"),
        ),
        schema="user",
    )

    # 🔥 project_id 추가 부분은 지운다 (이미 있음!!)
    # op.add_column(
    #     "practice_sessions",
    #     sa.Column(
    #         "project_id",
    #         sa.BigInteger(),
    #         nullable=True,
    #     ),
    #     schema="user",
    # )
    # FK 도 일단 생략 (이미 다른 리비전/수동으로 만들었을 수 있음)
    # op.create_foreign_key(...)

    # 2) created_at / updated_at 추가
    op.add_column(
        "practice_sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="user",
    )

    op.add_column(
        "practice_sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="user",
    )


def downgrade() -> None:
    # 역순으로 삭제
    op.drop_column("practice_sessions", "updated_at", schema="user")
    op.drop_column("practice_sessions", "created_at", schema="user")
    op.drop_column("practice_sessions", "status", schema="user")

    # project_id 는 이 리비전에서 안 건드렸으니까 여기서도 건들 필요 없음
