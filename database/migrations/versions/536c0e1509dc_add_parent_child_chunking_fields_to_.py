"""add parent-child chunking fields to document ingestion settings and document chunks

Revision ID: 536c0e1509dc
Revises: 564ef1c1a784
Create Date: 2025-12-22 15:53:34.083599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '536c0e1509dc'
down_revision: Union[str, Sequence[str], None] = '564ef1c1a784'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade() -> None:
    # ----------------------------
    # 1) user.document_ingestion_settings: add fields
    # ----------------------------
    with op.batch_alter_table("document_ingestion_settings", schema="user") as batch:
        batch.add_column(
            sa.Column(
                "chunking_mode",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'general'"),
            )
        )
        batch.add_column(sa.Column("segment_separator", sa.Text(), nullable=True))
        batch.add_column(sa.Column("parent_chunk_size", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("parent_chunk_overlap", sa.Integer(), nullable=True))

    # constraints (ingestion_settings)
    op.create_check_constraint(
        "chk_doc_ingest_chunking_mode_enum",
        "document_ingestion_settings",
        "chunking_mode IN ('general', 'parent_child')",
        schema="user",
    )
    op.create_check_constraint(
        "chk_doc_ingest_parent_overlap_ge_0_or_null",
        "document_ingestion_settings",
        "(parent_chunk_overlap IS NULL OR parent_chunk_overlap >= 0)",
        schema="user",
    )
    op.create_check_constraint(
        "chk_doc_ingest_parent_size_ge_1_or_null",
        "document_ingestion_settings",
        "(parent_chunk_size IS NULL OR parent_chunk_size >= 1)",
        schema="user",
    )
    op.create_check_constraint(
        "chk_doc_ingest_parent_overlap_lt_size_or_null",
        "document_ingestion_settings",
        "(parent_chunk_size IS NULL OR parent_chunk_overlap IS NULL OR parent_chunk_overlap < parent_chunk_size)",
        schema="user",
    )

    # ----------------------------
    # 2) user.document_chunks: add fields + relax nullable(vector/index) + constraints/indexes
    # ----------------------------

    # 기존 제약/인덱스 변경이 필요
    # - uq_document_chunks_doc_idx: 유지하되 chunk_index nullable로 바뀌므로 drop/recreate
    # - chk_document_chunks_index_ge_1: nullable 허용 버전으로 교체
    op.drop_constraint(
        "chk_document_chunks_index_ge_1",
        "document_chunks",
        schema="user",
        type_="check",
    )
    op.drop_constraint(
        "uq_document_chunks_doc_idx",
        "document_chunks",
        schema="user",
        type_="unique",
    )

    with op.batch_alter_table("document_chunks", schema="user") as batch:
        batch.add_column(
            sa.Column(
                "chunk_level",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'child'"),
            )
        )
        batch.add_column(sa.Column("parent_chunk_id", sa.BigInteger(), nullable=True))
        batch.add_column(
            sa.Column(
                "segment_index",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )
        batch.add_column(sa.Column("chunk_index_in_segment", sa.Integer(), nullable=True))

        # 기존 chunk_index를 nullable로 변경 (parent는 NULL 허용)
        batch.alter_column("chunk_index", existing_type=sa.Integer(), nullable=True)

        # vector_memory nullable로 변경 (parent는 NULL)
        batch.alter_column("vector_memory", nullable=True)

        # self FK
        # batch.create_foreign_key(
        #     "fk_document_chunks_parent_chunk_id",
        #     "document_chunks",
        #     ["parent_chunk_id"],
        #     ["chunk_id"],
        #     ondelete="SET NULL",
        # )
    op.create_foreign_key(
        "fk_document_chunks_parent_chunk_id",
        source_table="document_chunks",
        referent_table="document_chunks",
        local_cols=["parent_chunk_id"],
        remote_cols=["chunk_id"],
        source_schema="user",
        referent_schema="user",
        ondelete="SET NULL",
    )

    # document_chunks new constraints
    op.create_check_constraint(
        "chk_document_chunks_level_enum",
        "document_chunks",
        "chunk_level IN ('child', 'parent')",
        schema="user",
    )
    op.create_check_constraint(
        "chk_document_chunks_global_index_by_level",
        "document_chunks",
        "(chunk_level = 'parent' AND chunk_index IS NULL) OR (chunk_level = 'child' AND chunk_index IS NOT NULL)",
        schema="user",
    )
    op.create_check_constraint(
        "chk_document_chunks_index_ge_1_or_null",
        "document_chunks",
        "(chunk_index IS NULL OR chunk_index >= 1)",
        schema="user",
    )
    op.create_check_constraint(
        "chk_document_chunks_segment_index_ge_1",
        "document_chunks",
        "segment_index >= 1",
        schema="user",
    )
    op.create_check_constraint(
        "chk_document_chunks_index_in_segment_ge_1_or_null",
        "document_chunks",
        "(chunk_index_in_segment IS NULL OR chunk_index_in_segment >= 1)",
        schema="user",
    )
    op.create_check_constraint(
        "chk_document_chunks_parent_ref_allowed",
        "document_chunks",
        "(chunk_level = 'child' AND parent_chunk_id IS NOT NULL) "
        "OR (chunk_level = 'parent' AND parent_chunk_id IS NULL) "
        "OR (chunk_level = 'child' AND parent_chunk_id IS NULL)",
        schema="user",
    )
    op.create_check_constraint(
        "chk_document_chunks_vector_by_level",
        "document_chunks",
        "(chunk_level = 'child' AND vector_memory IS NOT NULL) OR (chunk_level = 'parent' AND vector_memory IS NULL)",
        schema="user",
    )

    # uniques / indexes
    op.create_unique_constraint(
        "uq_document_chunks_doc_idx",
        "document_chunks",
        ["knowledge_id", "chunk_index"],
        schema="user",
    )
    op.create_unique_constraint(
        "uq_document_chunks_doc_level_segment_idx",
        "document_chunks",
        ["knowledge_id", "chunk_level", "segment_index", "chunk_index_in_segment"],
        schema="user",
    )

    op.create_index(
        "idx_document_chunks_doc_level_segment",
        "document_chunks",
        ["knowledge_id", "chunk_level", "segment_index"],
        schema="user",
    )
    op.create_index(
        "idx_document_chunks_doc_parent",
        "document_chunks",
        ["knowledge_id", "parent_chunk_id"],
        schema="user",
    )

    # 기존 인덱스들은 이미 있을 수 있음 (충돌 나면 drop 후 create로 조정)
    # - idx_document_chunks_doc_index
    # - idx_document_chunks_doc_page
    # - idx_document_chunks_vec_ivfflat (이미 존재하면 유지)
    # 여기서는 새로 추가한 것만 생성


def downgrade() -> None:
    # ----------------------------
    # 1) user.document_chunks 되돌리기
    # ----------------------------
    # 새로 만든 인덱스/제약 제거
    op.drop_index("idx_document_chunks_doc_parent", table_name="document_chunks", schema="user")
    op.drop_index("idx_document_chunks_doc_level_segment", table_name="document_chunks", schema="user")

    op.drop_constraint(
        "uq_document_chunks_doc_level_segment_idx",
        "document_chunks",
        schema="user",
        type_="unique",
    )

    op.drop_constraint("chk_document_chunks_vector_by_level", "document_chunks", schema="user", type_="check")
    op.drop_constraint("chk_document_chunks_parent_ref_allowed", "document_chunks", schema="user", type_="check")
    op.drop_constraint("chk_document_chunks_index_in_segment_ge_1_or_null", "document_chunks", schema="user", type_="check")
    op.drop_constraint("chk_document_chunks_segment_index_ge_1", "document_chunks", schema="user", type_="check")
    op.drop_constraint("chk_document_chunks_index_ge_1_or_null", "document_chunks", schema="user", type_="check")
    op.drop_constraint("chk_document_chunks_global_index_by_level", "document_chunks", schema="user", type_="check")
    op.drop_constraint("chk_document_chunks_level_enum", "document_chunks", schema="user", type_="check")

    # uq_document_chunks_doc_idx는 다시 만들 거라 먼저 drop
    op.drop_constraint("uq_document_chunks_doc_idx", "document_chunks", schema="user", type_="unique")

    with op.batch_alter_table("document_chunks", schema="user") as batch:
        batch.drop_constraint("fk_document_chunks_parent_chunk_id", type_="foreignkey")
        batch.alter_column("vector_memory", nullable=False)
        batch.alter_column("chunk_index", existing_type=sa.Integer(), nullable=False)

        batch.drop_column("chunk_index_in_segment")
        batch.drop_column("segment_index")
        batch.drop_column("parent_chunk_id")
        batch.drop_column("chunk_level")

    # 원래 체크/유니크 복원
    op.create_check_constraint(
        "chk_document_chunks_index_ge_1",
        "document_chunks",
        "chunk_index >= 1",
        schema="user",
    )
    op.create_unique_constraint(
        "uq_document_chunks_doc_idx",
        "document_chunks",
        ["knowledge_id", "chunk_index"],
        schema="user",
    )

    # ----------------------------
    # 2) user.document_ingestion_settings 되돌리기
    # ----------------------------
    op.drop_constraint("chk_doc_ingest_parent_overlap_lt_size_or_null", "document_ingestion_settings", schema="user", type_="check")
    op.drop_constraint("chk_doc_ingest_parent_size_ge_1_or_null", "document_ingestion_settings", schema="user", type_="check")
    op.drop_constraint("chk_doc_ingest_parent_overlap_ge_0_or_null", "document_ingestion_settings", schema="user", type_="check")
    op.drop_constraint("chk_doc_ingest_chunking_mode_enum", "document_ingestion_settings", schema="user", type_="check")

    with op.batch_alter_table("document_ingestion_settings", schema="user") as batch:
        batch.drop_column("parent_chunk_overlap")
        batch.drop_column("parent_chunk_size")
        batch.drop_column("segment_separator")
        batch.drop_column("chunking_mode")