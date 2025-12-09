"""move document progress to documents table

Revision ID: 9822317db03c
Revises: 8a5b6de2acff
Create Date: 2025-12-05 16:01:52.836273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9822317db03c"
down_revision: Union[str, Sequence[str], None] = "8a5b6de2acff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) documents에 progress, error_message 추가
    op.add_column(
        "documents",
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        schema="user",
    )
    op.add_column(
        "documents",
        sa.Column("error_message", sa.Text(), nullable=True),
        schema="user",
    )

    # server_default 제거(원하면)
    op.alter_column(
        "documents",
        "progress",
        server_default=None,
        schema="user",
    )

    # 2) 기존 status 제약조건이 있다면 먼저 제거
    op.execute(
        'ALTER TABLE "user".documents '
        "DROP CONSTRAINT IF EXISTS chk_documents_status_enum"
    )

    # 3) 기존 status 값들을 새 enum 집합으로 매핑
    #    - 예전: processing -> embedding
    op.execute(
        """
        UPDATE "user".documents
        SET status = 'embedding'
        WHERE status = 'processing'
        """
    )

    #    - 예전: active -> ready
    op.execute(
        """
        UPDATE "user".documents
        SET status = 'ready'
        WHERE status = 'active'
        """
    )

    #    - 예전: error -> failed
    op.execute(
        """
        UPDATE "user".documents
        SET status = 'failed'
        WHERE status = 'error'
        """
    )

    #    - 혹시 NULL 이나 그 외 이상한 값 있으면 일단 ready 로 정리
    op.execute(
        """
        UPDATE "user".documents
        SET status = 'ready'
        WHERE status IS NULL
           OR status NOT IN ('uploading', 'embedding', 'ready', 'failed')
        """
    )

    # 4) status 체크 제약 재정의
    op.execute(
        """
        ALTER TABLE "user".documents
        ADD CONSTRAINT chk_documents_status_enum
        CHECK (status IN ('uploading', 'embedding', 'ready', 'failed'))
        """
    )

    # 5) document_processing_jobs 테이블 제거
    op.drop_table("document_processing_jobs", schema="user")


def downgrade() -> None:
    # 1) document_processing_jobs 복원
    op.create_table(
        "document_processing_jobs",
        sa.Column("job_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "knowledge_id",
            sa.BigInteger(),
            sa.ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "progress",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("step", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="chk_document_jobs_time",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="chk_document_jobs_progress_range",
        ),
        sa.Index("idx_document_jobs_doc_time", "knowledge_id", "started_at"),
        sa.Index("idx_document_jobs_status", "status"),
        schema="user",
    )

    # 2) documents에서 progress, error_message 제거
    op.drop_column("documents", "error_message", schema="user")
    op.drop_column("documents", "progress", schema="user")