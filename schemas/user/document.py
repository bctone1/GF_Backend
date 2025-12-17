# schemas/user/document.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, List, Literal

from pydantic import ConfigDict, Field, model_validator

from schemas.base import ORMBase


# =========================================================
# Constants (정합성 고정)
# =========================================================
EMBEDDING_DIM_FIXED: Literal[1536] = 1536
KB_SCORE_TYPE_FIXED: Literal["cosine_similarity"] = "cosine_similarity"

ChunkStrategy = Literal["recursive", "token", "semantic"]


# =========================================================
# user.documents
# =========================================================
class DocumentCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    owner_id: int
    name: str
    file_format: str
    file_size_bytes: int
    folder_path: Optional[str] = None

    status: Optional[str] = None           # default: 'uploading'
    chunk_count: Optional[int] = None      # default: 0
    progress: Optional[int] = None         # default: 0
    error_message: Optional[str] = None    # default: None
    uploaded_at: Optional[datetime] = None


class DocumentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    name: Optional[str] = None
    folder_path: Optional[str] = None
    status: Optional[str] = None
    chunk_count: Optional[int] = None
    progress: Optional[int] = None
    error_message: Optional[str] = None
    # updated_at는 서버 관리


class DocumentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    knowledge_id: int
    owner_id: int
    name: str
    file_format: str
    file_size_bytes: int
    folder_path: Optional[str] = None

    status: str          # 'uploading' / 'embedding' / 'ready' / 'failed'
    chunk_count: int
    progress: int        # 0 ~ 100
    error_message: Optional[str] = None

    uploaded_at: datetime
    updated_at: datetime


# =========================================================
# user.document_ingestion_settings
# =========================================================
class DocumentIngestionSettingCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    knowledge_id: int

    chunk_size: int = Field(ge=1)
    chunk_overlap: int = Field(ge=0)
    max_chunks: int = Field(ge=1)
    chunk_strategy: ChunkStrategy

    embedding_provider: str
    embedding_model: str

    # 1536만 허용(정합성)
    embedding_dim: Literal[1536] = EMBEDDING_DIM_FIXED

    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")
        return self


class DocumentIngestionSettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    chunk_size: Optional[int] = Field(default=None, ge=1)
    chunk_overlap: Optional[int] = Field(default=None, ge=0)
    max_chunks: Optional[int] = Field(default=None, ge=1)
    chunk_strategy: Optional[ChunkStrategy] = None

    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None

    # 업데이트로 다른 값 못 넣게 (넣는다면 1536만)
    embedding_dim: Optional[Literal[1536]] = None

    extra: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def _validate_overlap(self):
        # 부분 업데이트라 둘 다 있을 때만 체크
        if self.chunk_size is not None and self.chunk_overlap is not None:
            if self.chunk_overlap >= self.chunk_size:
                raise ValueError("chunk_overlap must be < chunk_size")
        return self


class DocumentIngestionSettingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    knowledge_id: int

    chunk_size: int
    chunk_overlap: int
    max_chunks: int
    chunk_strategy: str

    embedding_provider: str
    embedding_model: str
    embedding_dim: int

    extra: dict[str, Any]

    created_at: datetime
    updated_at: datetime


# =========================================================
# user.document_search_settings
# =========================================================
class DocumentSearchSettingCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    knowledge_id: int

    top_k: int = Field(ge=1)

    # 유사도(min_score) 기준 (0~1)
    min_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))

    # 고정(혼용 금지)
    score_type: Literal["cosine_similarity"] = KB_SCORE_TYPE_FIXED

    reranker_enabled: bool = False
    reranker_model: Optional[str] = None
    reranker_top_n: int = Field(ge=1)

    @model_validator(mode="after")
    def _validate_reranker_top_n(self):
        if self.reranker_top_n > self.top_k:
            raise ValueError("reranker_top_n must be <= top_k")
        return self


class DocumentSearchSettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    top_k: Optional[int] = Field(default=None, ge=1)
    min_score: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("1"))

    # 업데이트로 다른 값 못 넣게 (넣는다면 cosine_similarity만)
    score_type: Optional[Literal["cosine_similarity"]] = None

    reranker_enabled: Optional[bool] = None
    reranker_model: Optional[str] = None
    reranker_top_n: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_reranker_top_n(self):
        # 부분 업데이트라 둘 다 있을 때만 체크
        if self.top_k is not None and self.reranker_top_n is not None:
            if self.reranker_top_n > self.top_k:
                raise ValueError("reranker_top_n must be <= top_k")
        return self


class DocumentSearchSettingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    knowledge_id: int
    top_k: int
    min_score: Decimal
    score_type: str

    reranker_enabled: bool
    reranker_model: Optional[str] = None
    reranker_top_n: int

    created_at: datetime
    updated_at: datetime


# =========================================================
# Chunk Preview DTO (저장 안 함)
# =========================================================
class ChunkPreviewRequest(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    chunk_size: int = Field(ge=1)
    chunk_overlap: int = Field(ge=0)
    max_chunks: int = Field(ge=1)
    chunk_strategy: ChunkStrategy = "recursive"

    @model_validator(mode="after")
    def _validate_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")
        return self


class ChunkPreviewItem(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    chunk_index: int
    text: str
    char_count: int
    approx_tokens: Optional[int] = None


class ChunkPreviewStats(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    total_chunks: int
    total_chars: int
    approx_total_tokens: Optional[int] = None


class ChunkPreviewResponse(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    items: List[ChunkPreviewItem]
    stats: ChunkPreviewStats


# =========================================================
# user.document_usage
# =========================================================
class DocumentUsageCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    knowledge_id: int
    user_id: Optional[int] = None
    usage_type: str
    usage_count: Optional[int] = None      # server default 0
    last_used_at: Optional[datetime] = None


class DocumentUsageUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    usage_type: Optional[str] = None
    usage_count: Optional[int] = None
    last_used_at: Optional[datetime] = None


class DocumentUsageResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    usage_id: int
    knowledge_id: int
    user_id: Optional[int] = None
    usage_type: str
    usage_count: int
    last_used_at: datetime


# =========================================================
# user.document_pages
# =========================================================
class DocumentPageCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    knowledge_id: int
    page_no: Optional[int] = None          # 1부터, NULL 허용
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None  # 보통 서버에서 채움


class DocumentPageUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    page_no: Optional[int] = None
    image_url: Optional[str] = None
    # created_at은 보통 수정 안 함


class DocumentPageResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    page_id: int
    knowledge_id: int
    page_no: Optional[int] = None
    image_url: Optional[str] = None
    created_at: datetime


# =========================================================
# user.document_chunks
# =========================================================
class DocumentChunkCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    knowledge_id: int
    page_id: Optional[int] = None
    chunk_index: int
    chunk_text: str
    created_at: Optional[datetime] = None


class DocumentChunkUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    page_id: Optional[int] = None
    chunk_index: Optional[int] = None
    chunk_text: Optional[str] = None
    # vector_memory는 외부에서 직접 갱신 안 하는 전제


class DocumentChunkResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: int
    knowledge_id: int
    page_id: Optional[int] = None
    chunk_index: int
    chunk_text: str
    created_at: datetime
    # vector_memory는 보통 외부로 내보내지 않음
