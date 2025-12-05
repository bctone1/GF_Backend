# models/user/document.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from models.base import Base

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

    chunk_count = Column(Integer, nullable=False, server_default=text("0"))

    # 진행률 (0~100)
    progress = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    # 실패 시 에러 메시지 (성공 시 NULL)
    error_message = Column(Text, nullable=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 관계들 (jobs 제거)
    tags = relationship("DocumentTagAssignment", back_populates="document", passive_deletes=True)
    usages = relationship("DocumentUsage", back_populates="document", passive_deletes=True)
    pages = relationship("DocumentPage", back_populates="document", passive_deletes=True)
    chunks = relationship("DocumentChunk", back_populates="document", passive_deletes=True)

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


# ========== user.document_tags ==========
class DocumentTag(Base):
    __tablename__ = "document_tags"

    tag_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)

    __table_args__ = (
        Index("idx_document_tags_name", "name"),
        {"schema": "user"},
    )


# ========== user.document_tag_assignments ==========
class DocumentTagAssignment(Base):
    __tablename__ = "document_tag_assignments"

    assignment_id = Column(BigInteger, primary_key=True, autoincrement=True)

    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id = Column(
        BigInteger,
        ForeignKey("user.document_tags.tag_id", ondelete="CASCADE"),
        nullable=False,
    )

    document = relationship("Document", back_populates="tags", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("knowledge_id", "tag_id", name="uq_document_tag_assignments_doc_tag"),
        Index("idx_document_tag_assignments_doc", "knowledge_id"),
        Index("idx_document_tag_assignments_tag", "tag_id"),
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

    usage_type = Column(Text, nullable=False)   # e.g., 'rag_query','preview','download'
    usage_count = Column(Integer, nullable=False, server_default=text("0"))
    last_used_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="usages", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("usage_count >= 0", name="chk_document_usage_count_nonneg"),
        Index("idx_document_usage_doc_time", "knowledge_id", "last_used_at"),
        Index("idx_document_usage_user_time", "user_id", "last_used_at"),
        {"schema": "user"},
    )


# ========== user.document_pages (기존 KnowledgePage 리팩토링) ==========
class DocumentPage(Base):
    __tablename__ = "document_pages"

    page_id = Column(BigInteger, primary_key=True, autoincrement=True)

    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="CASCADE"),
        nullable=False,
    )

    page_no = Column(Integer, nullable=True)       # 1부터
    image_url = Column(Text, nullable=True)        # WebP 권장 (옵션)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="pages", passive_deletes=True)
    chunks = relationship("DocumentChunk", back_populates="page", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("knowledge_id", "page_no", name="uq_document_pages_doc_page"),
        CheckConstraint("page_no IS NULL OR page_no >= 1", name="chk_document_pages_page_no_ge_1"),
        Index("idx_document_pages_doc_page", "knowledge_id", "page_no"),
        {"schema": "user"},
    )


# ========== user.document_chunks (기존 KnowledgeChunk 리팩토링) ==========
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

    chunk_index = Column(Integer, nullable=False)  # 1부터
    chunk_text = Column(Text, nullable=False)
    vector_memory = Column(Vector(1536), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="chunks", passive_deletes=True)
    page = relationship("DocumentPage", back_populates="chunks", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("chunk_index >= 1", name="chk_document_chunks_index_ge_1"),
        UniqueConstraint("knowledge_id", "chunk_index", name="uq_document_chunks_doc_idx"),
        Index("idx_document_chunks_doc_index", "knowledge_id", "chunk_index"),
        Index("idx_document_chunks_doc_page", "knowledge_id", "page_id"),
        Index(
            "idx_document_chunks_vec_ivfflat",
            "vector_memory",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"vector_memory": "vector_cosine_ops"},
        ),
        {"schema": "user"},
    )
