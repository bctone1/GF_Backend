"""20251217_add_document_settings

Revision ID: ac81cd797f6f
Revises: 98fd45d5c846
Create Date: 2025-12-17 11:33:57.379061

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac81cd797f6f'
down_revision: Union[str, Sequence[str], None] = '98fd45d5c846'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



EMBEDDING_DIM_FIXED = 1536
KB_SCORE_TYPE_FIXED = "cosine_similarity"


def upgrade() -> None:
    # 1) user.document_ingestion_settings
    from sqlalchemy.dialects import postgresql
    op.create_table(
        "document_ingestion_settings",
        sa.Column(
            "knowledge_id",
            sa.BigInteger(),
            sa.ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("max_chunks", sa.Integer(), nullable=False),
        sa.Column("chunk_strategy", sa.Text(), nullable=False),
        sa.Column("embedding_provider", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column(
            "embedding_dim",
            sa.Integer(),
            nullable=False,
            server_default=sa.text(str(EMBEDDING_DIM_FIXED)),
        ),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("chunk_size >= 1", name="chk_doc_ingest_chunk_size_ge_1"),
        sa.CheckConstraint("chunk_overlap >= 0", name="chk_doc_ingest_chunk_overlap_ge_0"),
        sa.CheckConstraint("chunk_overlap < chunk_size", name="chk_doc_ingest_overlap_lt_size"),
        sa.CheckConstraint("max_chunks >= 1", name="chk_doc_ingest_max_chunks_ge_1"),
        sa.CheckConstraint(
            f"embedding_dim = {EMBEDDING_DIM_FIXED}",
            name="chk_doc_ingest_embedding_dim_fixed_1536",
        ),
        schema="user",
    )

    # 2) user.document_search_settings
    op.create_table(
        "document_search_settings",
        sa.Column(
            "knowledge_id",
            sa.BigInteger(),
            sa.ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("min_score", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "score_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text(f"'{KB_SCORE_TYPE_FIXED}'"),
        ),
        sa.Column(
            "reranker_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("reranker_model", sa.Text(), nullable=True),
        sa.Column("reranker_top_n", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("top_k >= 1", name="chk_doc_search_top_k_ge_1"),
        sa.CheckConstraint("min_score >= 0 AND min_score <= 1", name="chk_doc_search_min_score_0_1"),
        sa.CheckConstraint("reranker_top_n >= 1", name="chk_doc_search_reranker_top_n_ge_1"),
        sa.CheckConstraint("reranker_top_n <= top_k", name="chk_doc_search_reranker_top_n_le_top_k"),
        sa.CheckConstraint(
            f"score_type = '{KB_SCORE_TYPE_FIXED}'",
            name="chk_doc_search_score_type_fixed_cos_sim",
        ),
        schema="user",
    )


def downgrade() -> None:
    op.drop_table("document_search_settings", schema="user")
    op.drop_table("document_ingestion_settings", schema="user")
