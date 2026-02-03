# models/user/document.py
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    Integer,
    DateTime,
    Numeric,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from models.base import Base

EMBEDDING_DIM_FIXED = 1536  # postgreSQL 현재 1536만 됨 small model고정
KB_SCORE_TYPE_FIXED = "cosine_similarity"  # 유사도 기반으로 고정


# ========== user.documents ==========
class Document(Base):
    __tablename__ = "documents"

    knowledge_id = Column(BigInteger, primary_key=True, autoincrement=True)

    owner_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    name = Column(Text, nullable=False)
    file_format = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    folder_path = Column(Text, nullable=True)

    # status: uploading -> embedding(서버 처리 단계) -> ready / failed
    status = Column(
        Text,
        nullable=False,
        server_default=text("'uploading'"),
    )

    # NOTE: chunk_count는 "검색용(child) 청크 수"로 유지 권장
    chunk_count = Column(Integer, nullable=False, server_default=text("0"))

    # 진행률 (0~100)
    progress = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    # 실패 시 에러 메시지 (성공 시 NULL)
    error_message = Column(Text, nullable=True)

    # RAG UI 모드: simple(간단 업로드), advanced(고급 설정), compare(비교 분석)
    rag_ui_mode = Column(Text, nullable=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 관계들 (tags 제거)
    usages = relationship("DocumentUsage", back_populates="document", passive_deletes=True)
    pages = relationship("DocumentPage", back_populates="document", passive_deletes=True)
    chunks = relationship("DocumentChunk", back_populates="document", passive_deletes=True)

    # 1:1 설정 관계 (문서당 1개)
    ingestion_setting = relationship(
        "DocumentIngestionSetting",
        back_populates="document",
        uselist=False,
        passive_deletes=True,
    )
    search_setting = relationship(
        "DocumentSearchSetting",
        back_populates="document",
        uselist=False,
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("file_size_bytes >= 0", name="chk_documents_size_nonneg"),
        CheckConstraint("chunk_count >= 0", name="chk_documents_chunk_nonneg"),
        CheckConstraint(
            "status IN ('uploading', 'embedding', 'ready', 'failed')",
            name="chk_documents_status_enum",
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="chk_documents_progress_range",
        ),
        CheckConstraint(
            "rag_ui_mode IS NULL OR rag_ui_mode IN ('simple', 'advanced', 'compare')",
            name="chk_documents_rag_ui_mode_enum",
        ),
        Index("idx_documents_owner_time", "owner_id", "uploaded_at"),
        Index("idx_documents_status_time", "status", "uploaded_at"),
        Index(
            "idx_documents_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        {"schema": "user"},
    )


# ========== user.document_ingestion_settings ==========
class DocumentIngestionSetting(Base):
    """
    문서당 1개 row 강제:
    - knowledge_id = PK + FK (CASCADE)
    - embedding_dim은 1536만 허용(벡터 컬럼 차원과 정합성)
    """
    __tablename__ = "document_ingestion_settings"

    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # -------------------------
    # chunking (child 기준)
    # -------------------------
    chunk_size = Column(Integer, nullable=False)
    chunk_overlap = Column(Integer, nullable=False)
    max_chunks = Column(Integer, nullable=False)
    chunk_strategy = Column(Text, nullable=False)

    # -------------------------
    # parent-child 확장 옵션
    # - 일반 모드: chunking_mode='general', segment_separator NULL 가능
    # - 부모-자식: chunking_mode='parent_child', segment_separator 사용 + parent_* 사용
    # -------------------------
    chunking_mode = Column(Text, nullable=False, server_default=text("'general'"))  # general | parent_child
    segment_separator = Column(Text, nullable=True)  # 예: '\n\n', '#h#h', '## '

    parent_chunk_size = Column(Integer, nullable=True)
    parent_chunk_overlap = Column(Integer, nullable=True)

    # -------------------------
    # embedding
    # -------------------------
    embedding_provider = Column(Text, nullable=False)
    embedding_model = Column(Text, nullable=False)

    # 정합성 강제: 1536 차원 only
    embedding_dim = Column(Integer, nullable=False, server_default=text(str(EMBEDDING_DIM_FIXED)))

    # 전처리 옵션/기타 확장
    extra = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    document = relationship("Document", back_populates="ingestion_setting", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("chunk_size >= 1", name="chk_doc_ingest_chunk_size_ge_1"),
        CheckConstraint("chunk_overlap >= 0", name="chk_doc_ingest_chunk_overlap_ge_0"),
        CheckConstraint("chunk_overlap < chunk_size", name="chk_doc_ingest_overlap_lt_size"),
        CheckConstraint("max_chunks >= 1", name="chk_doc_ingest_max_chunks_ge_1"),
        CheckConstraint(
            f"embedding_dim = {EMBEDDING_DIM_FIXED}",
            name="chk_doc_ingest_embedding_dim_fixed_1536",
        ),
        CheckConstraint(
            "chunking_mode IN ('general', 'parent_child')",
            name="chk_doc_ingest_chunking_mode_enum",
        ),
        # parent_* 정합성
        CheckConstraint(
            "(parent_chunk_overlap IS NULL OR parent_chunk_overlap >= 0)",
            name="chk_doc_ingest_parent_overlap_ge_0_or_null",
        ),
        CheckConstraint(
            "(parent_chunk_size IS NULL OR parent_chunk_size >= 1)",
            name="chk_doc_ingest_parent_size_ge_1_or_null",
        ),
        CheckConstraint(
            "(parent_chunk_size IS NULL OR parent_chunk_overlap IS NULL OR parent_chunk_overlap < parent_chunk_size)",
            name="chk_doc_ingest_parent_overlap_lt_size_or_null",
        ),
        {"schema": "user"},
    )


# ========== user.document_search_settings ==========
class DocumentSearchSetting(Base):
    """
    검색 설정도 문서당 1개 row 강제.
    - min_score(유사도) 기준으로 통일
    - score_type도 cosine_similarity로 고정 (혼용 금지)
    """
    __tablename__ = "document_search_settings"

    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
        primary_key=True,
    )

    top_k = Column(Integer, nullable=False)

    # 유사도(min_score) 기준
    min_score = Column(Numeric(10, 6), nullable=False)
    score_type = Column(Text, nullable=False, server_default=text(f"'{KB_SCORE_TYPE_FIXED}'"))

    reranker_enabled = Column(Boolean, nullable=False, server_default=text("false"))
    reranker_model = Column(Text, nullable=True)
    reranker_top_n = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    document = relationship("Document", back_populates="search_setting", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("top_k >= 1", name="chk_doc_search_top_k_ge_1"),
        CheckConstraint("min_score >= 0 AND min_score <= 1", name="chk_doc_search_min_score_0_1"),
        CheckConstraint("reranker_top_n >= 1", name="chk_doc_search_reranker_top_n_ge_1"),
        CheckConstraint("reranker_top_n <= top_k", name="chk_doc_search_reranker_top_n_le_top_k"),
        CheckConstraint(
            f"score_type = '{KB_SCORE_TYPE_FIXED}'",
            name="chk_doc_search_score_type_fixed_cos_sim",
        ),
        {"schema": "user"},
    )


# ========== user.document_usage ==========
class DocumentUsage(Base):
    __tablename__ = "document_usage"

    usage_id = Column(BigInteger, primary_key=True, autoincrement=True)

    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    usage_type = Column(Text, nullable=False)  # e.g., 'rag_query','preview','download'
    usage_count = Column(Integer, nullable=False, server_default=text("0"))
    last_used_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="usages", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("usage_count >= 0", name="chk_document_usage_count_nonneg"),
        Index("idx_document_usage_doc_time", "knowledge_id", "last_used_at"),
        Index("idx_document_usage_user_time", "user_id", "last_used_at"),
        {"schema": "user"},
    )


# ========== user.document_pages ==========
class DocumentPage(Base):
    __tablename__ = "document_pages"

    page_id = Column(BigInteger, primary_key=True, autoincrement=True)

    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )

    page_no = Column(Integer, nullable=True)  # 1부터
    image_url = Column(Text, nullable=True)  # WebP 권장 (옵션)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="pages", passive_deletes=True)
    chunks = relationship("DocumentChunk", back_populates="page", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("knowledge_id", "page_no", name="uq_document_pages_doc_page"),
        CheckConstraint("page_no IS NULL OR page_no >= 1", name="chk_document_pages_page_no_ge_1"),
        Index("idx_document_pages_doc_page", "knowledge_id", "page_no"),
        {"schema": "user"},
    )


# ========== user.document_chunks ==========
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    page_id = Column(
        BigInteger,
        ForeignKey("user.document_pages.page_id", ondelete="SET NULL"),
        nullable=True,
    )

    # parent-child 확장
    chunk_level = Column(Text, nullable=False, server_default=text("'child'"))  # child | parent
    parent_chunk_id = Column(
        BigInteger,
        ForeignKey("user.document_chunks.chunk_id", ondelete="SET NULL"),
        nullable=True,
    )
    segment_index = Column(Integer, nullable=False, server_default=text("1"))  # 1부터 (일반 모드=1 고정)
    chunk_index_in_segment = Column(Integer, nullable=True)  # 1부터 (child에서만 채우기 권장)

    # 문서 전체에서 증가하는 인덱스 (기존 유지)
    # - 일반 모드: child만 존재 -> 1..N
    # - 부모-자식 모드: child에서만 1..N, parent는 NULL 허용
    chunk_index = Column(Integer, nullable=True)
    chunk_text = Column(Text, nullable=False)

    # 벡터 차원 고정
    # - child: NOT NULL
    # - parent: NULL (권장)
    vector_memory = Column(Vector(EMBEDDING_DIM_FIXED), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="chunks", passive_deletes=True)
    page = relationship("DocumentPage", back_populates="chunks", passive_deletes=True)

    __table_args__ = (
        CheckConstraint(
            "chunk_level IN ('child', 'parent')",
            name="chk_document_chunks_level_enum",
        ),
        # 인덱스 정합성
        CheckConstraint(
            "(chunk_level = 'parent' AND chunk_index IS NULL) OR (chunk_level = 'child' AND chunk_index IS NOT NULL)",
            name="chk_document_chunks_global_index_by_level",
        ),
        CheckConstraint(
            "(chunk_index IS NULL OR chunk_index >= 1)",
            name="chk_document_chunks_index_ge_1_or_null",
        ),
        CheckConstraint(
            "segment_index >= 1",
            name="chk_document_chunks_segment_index_ge_1",
        ),
        CheckConstraint(
            "(chunk_index_in_segment IS NULL OR chunk_index_in_segment >= 1)",
            name="chk_document_chunks_index_in_segment_ge_1_or_null",
        ),
        # parent-child 관계 정합성
        CheckConstraint(
            "(chunk_level = 'child' AND parent_chunk_id IS NOT NULL) OR (chunk_level = 'parent' AND parent_chunk_id IS NULL) "
            "OR (chunk_level = 'child' AND parent_chunk_id IS NULL)",  # 일반모드(child 단일) 허용
            name="chk_document_chunks_parent_ref_allowed",
        ),
        # 벡터 정합성: child는 벡터 필수, parent는 벡터 비움(권장)
        CheckConstraint(
            "(chunk_level = 'child' AND vector_memory IS NOT NULL) OR (chunk_level = 'parent' AND vector_memory IS NULL)",
            name="chk_document_chunks_vector_by_level",
        ),
        # 문서 내 글로벌 인덱스 unique (NULL 여러 개 허용 -> parent 여러 개 OK)
        UniqueConstraint("knowledge_id", "chunk_index", name="uq_document_chunks_doc_idx"),
        # 세그먼트 내 인덱스 unique (parent/child 포함해서 충돌 방지)
        UniqueConstraint(
            "knowledge_id",
            "chunk_level",
            "segment_index",
            "chunk_index_in_segment",
            name="uq_document_chunks_doc_level_segment_idx",
        ),
        Index("idx_document_chunks_doc_level_segment", "knowledge_id", "chunk_level", "segment_index"),
        Index("idx_document_chunks_doc_parent", "knowledge_id", "parent_chunk_id"),
        Index("idx_document_chunks_doc_index", "knowledge_id", "chunk_index"),
        Index("idx_document_chunks_doc_page", "knowledge_id", "page_id"),
        # NOTE: ivfflat 인덱스는 vector_memory NULL 허용이어도 생성 가능하지만,
        #       쿼리는 child만 대상으로 걸도록(WHERE chunk_level='child') 구성 권장.
        Index(
            "idx_document_chunks_vec_ivfflat",
            "vector_memory",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"vector_memory": "vector_cosine_ops"},
        ),
        {"schema": "user"},
    )
