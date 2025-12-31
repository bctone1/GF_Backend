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

DEFAULT_CHILD_CHUNK_SIZE = 800
DEFAULT_CHILD_CHUNK_OVERLAP = 200
DEFAULT_MAX_CHUNKS = 100
DEFAULT_CHUNK_STRATEGY: Literal["recursive"] = "recursive"

DEFAULT_EMBEDDING_PROVIDER = "openai"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dim과 정합

DEFAULT_PARENT_CHILD_SEPARATOR: Literal["\n\n"] = "\n\n"

DEFAULT_PARENT_CHUNK_SIZE = 4000
DEFAULT_PARENT_CHUNK_OVERLAP = 400


ChunkStrategy = Literal["recursive", "token", "semantic"]
ChunkingMode = Literal["general", "parent_child"]
ChunkLevel = Literal["child", "parent"]



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

    status: Optional[str] = None  # default: 'uploading'
    chunk_count: Optional[int] = None  # default: 0
    progress: Optional[int] = None  # default: 0
    error_message: Optional[str] = None  # default: None
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

    status: str  # 'uploading' / 'embedding' / 'ready' / 'failed'
    chunk_count: int
    progress: int  # 0 ~ 100
    error_message: Optional[str] = None

    uploaded_at: datetime
    updated_at: datetime



# =========================================================
# user.document_ingestion_settings
# =========================================================
class DocumentIngestionSettingCreate(ORMBase):
    model_config = ConfigDict(
        from_attributes=False,
        json_schema_extra={
            "examples": [
                {
                    "chunk_size": 800,
                    "chunk_overlap": 200,
                    "max_chunks": 100,
                    "chunk_strategy": "recursive",
                    "chunking_mode": "general",
                    "embedding_provider": "openai",
                    "embedding_model": "text-embedding-3-small",
                    "embedding_dim": 1536,
                    "extra": {},
                },
                {
                    "chunk_size": 800,
                    "chunk_overlap": 200,
                    "max_chunks": 100,
                    "chunk_strategy": "recursive",
                    "chunking_mode": "parent_child",
                    "segment_separator": "\n\n",
                    "parent_chunk_size": 4000,
                    "parent_chunk_overlap": 400,
                    "embedding_provider": "openai",
                    "embedding_model": "text-embedding-3-small",
                    "embedding_dim": 1536,
                    "extra": {},
                },
            ]
        },
    )

    knowledge_id: int

    # child chunking (추천 default)
    chunk_size: int = Field(default=DEFAULT_CHILD_CHUNK_SIZE, ge=1)
    chunk_overlap: int = Field(default=DEFAULT_CHILD_CHUNK_OVERLAP, ge=0)
    max_chunks: int = Field(default=DEFAULT_MAX_CHUNKS, ge=1)
    chunk_strategy: ChunkStrategy = DEFAULT_CHUNK_STRATEGY

    # mode
    chunking_mode: ChunkingMode = "general"
    segment_separator: Optional[str] = Field(default=None, min_length=1, max_length=64)

    # parent chunking (parent_child에서만 의미)
    parent_chunk_size: Optional[int] = Field(default=None, ge=1)
    parent_chunk_overlap: Optional[int] = Field(default=None, ge=0)

    # embedding (추천 default)
    embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER
    embedding_model: str = DEFAULT_EMBEDDING_MODEL

    embedding_dim: Literal[1536] = EMBEDDING_DIM_FIXED
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_overlap_and_mode(self):
        # MVP: recursive만
        if self.chunk_strategy != "recursive":
            raise ValueError("unsupported chunk_strategy (MVP): only 'recursive' is allowed")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")

        if self.chunking_mode == "parent_child":
            # 디폴트 separator 채움 (Swagger/프론트도 직관적으로)
            if self.segment_separator is None:
                self.segment_separator = DEFAULT_PARENT_CHILD_SEPARATOR

            if self.parent_chunk_size is not None and self.parent_chunk_overlap is not None:
                if self.parent_chunk_overlap >= self.parent_chunk_size:
                    raise ValueError("parent_chunk_overlap must be < parent_chunk_size")
        else:
            # general이면 의미 없는 값은 정리
            self.segment_separator = None
            self.parent_chunk_size = None
            self.parent_chunk_overlap = None

        # 위험한 separator 최소 방어(개행은 허용해야 해서 strip() 검사는 금지)
        if self.segment_separator is not None:
            if self.segment_separator == "":
                raise ValueError("segment_separator cannot be empty string")
            if self.segment_separator in (" ", ".", ","):
                raise ValueError("segment_separator is too generic (would explode segments)")

        return self



DEFAULT_PARENT_CHILD_SEPARATOR = "\n\n"

class DocumentIngestionSettingUpdate(ORMBase):
    model_config = ConfigDict(
        from_attributes=False,
        json_schema_extra={
            "examples": [
                {
                    "chunk_size": 800,
                    "chunk_overlap": 200,
                    "max_chunks": 100,
                    "chunk_strategy": "recursive",
                    "chunking_mode": "general",
                    "segment_separator": "\n\n",
                    "embedding_provider": "openai",
                    "embedding_model": "text-embedding-3-small",
                    "extra": {},
                },
                {
                    "chunking_mode": "parent_child",
                    "segment_separator": "\n\n",
                    "chunk_size": 800,
                    "chunk_overlap": 200,
                    "max_chunks": 100,
                    "chunk_strategy": "recursive",
                },
            ]
        },
    )

    chunk_size: Optional[int] = Field(default=None, ge=1)
    chunk_overlap: Optional[int] = Field(default=None, ge=0)
    max_chunks: Optional[int] = Field(default=None, ge=1)
    chunk_strategy: Optional[ChunkStrategy] = None

    chunking_mode: Optional[ChunkingMode] = None


    segment_separator: Optional[str] = Field(
        default=DEFAULT_PARENT_CHILD_SEPARATOR,
        min_length=1,
        max_length=64,
    )

    parent_chunk_size: Optional[int] = Field(default=None, ge=1)
    parent_chunk_overlap: Optional[int] = Field(default=None, ge=0)

    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dim: Optional[Literal[1536]] = None
    extra: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def _validate(self):
        if self.chunk_strategy is not None and self.chunk_strategy != "recursive":
            raise ValueError("unsupported chunk_strategy (MVP): only 'recursive' is allowed")

        if self.chunk_size is not None and self.chunk_overlap is not None:
            if self.chunk_overlap >= self.chunk_size:
                raise ValueError("chunk_overlap must be < chunk_size")

        if self.parent_chunk_size is not None and self.parent_chunk_overlap is not None:
            if self.parent_chunk_overlap >= self.parent_chunk_size:
                raise ValueError("parent_chunk_overlap must be < parent_chunk_size")

        if self.segment_separator is not None:
            if self.segment_separator == "":
                raise ValueError("segment_separator cannot be empty string")
            if self.segment_separator in (" ", ".", ","):
                raise ValueError("segment_separator is too generic (would explode segments)")

        # general로 명시하면 parent 관련 정리
        if self.chunking_mode == "general":
            self.segment_separator = None
            self.parent_chunk_size = None
            self.parent_chunk_overlap = None

        # parent_child로 명시했는데 segment_separator를 null로 보낸 건 막기
        if self.chunking_mode == "parent_child":
            if "segment_separator" in self.model_fields_set and self.segment_separator is None:
                raise ValueError("segment_separator cannot be null when chunking_mode='parent_child'")

            # 아예 안 보냈으면 디폴트(\n\n) 주입 (UX)
            if "segment_separator" not in self.model_fields_set and self.segment_separator is None:
                self.segment_separator = DEFAULT_PARENT_CHILD_SEPARATOR

        return self



class DocumentIngestionSettingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    knowledge_id: int

    # child chunking
    chunk_size: int
    chunk_overlap: int
    max_chunks: int
    chunk_strategy: ChunkStrategy

    # mode
    chunking_mode: ChunkingMode
    segment_separator: Optional[str] = None
    parent_chunk_size: Optional[int] = None
    parent_chunk_overlap: Optional[int] = None

    embedding_provider: str
    embedding_model: str
    embedding_dim: Literal[1536]

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
    model_config = ConfigDict(
        from_attributes=False,
        json_schema_extra={
            "examples": [
                {
                    "chunk_size": 800,
                    "chunk_overlap": 200,
                    "max_chunks": 100,
                    "chunk_strategy": "recursive",
                    "chunking_mode": "general",
                    "segment_separator": "\n\n",
                },
                {
                    "chunk_size": 800,
                    "chunk_overlap": 200,
                    "max_chunks": 100,
                    "chunk_strategy": "recursive",
                    "chunking_mode": "parent_child",
                    "segment_separator": "\n\n",
                    "parent_chunk_size": 4000,
                    "parent_chunk_overlap": 400,
                },
            ]
        },
    )

    chunk_size: int = Field(default=DEFAULT_CHILD_CHUNK_SIZE, ge=1)
    chunk_overlap: int = Field(default=DEFAULT_CHILD_CHUNK_OVERLAP, ge=0)
    max_chunks: int = Field(default=DEFAULT_MAX_CHUNKS, ge=1)
    chunk_strategy: ChunkStrategy = DEFAULT_CHUNK_STRATEGY

    chunking_mode: ChunkingMode = "general"
    segment_separator: Optional[str] = Field(default=None, min_length=1, max_length=64)
    parent_chunk_size: Optional[int] = Field(default=None, ge=1)
    parent_chunk_overlap: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate(self):
        if self.chunk_strategy != "recursive":
            raise ValueError("unsupported chunk_strategy : only 'recursive' is allowed")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")

        if self.chunking_mode == "parent_child":
            if self.segment_separator is None:
                self.segment_separator = DEFAULT_PARENT_CHILD_SEPARATOR

            if self.parent_chunk_size is not None and self.parent_chunk_overlap is not None:
                if self.parent_chunk_overlap >= self.parent_chunk_size:
                    raise ValueError("parent_chunk_overlap must be < parent_chunk_size")
        else:
            self.segment_separator = None
            self.parent_chunk_size = None
            self.parent_chunk_overlap = None

        if self.segment_separator is not None:
            if self.segment_separator == "":
                raise ValueError("segment_separator cannot be empty string")
            if self.segment_separator in (" ", ".", ","):
                raise ValueError("segment_separator is too generic (would explode segments)")

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
    usage_count: Optional[int] = None  # server default 0
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
    page_no: Optional[int] = None  # 1부터, NULL 허용
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None  # 보통 서버에서 채움


class DocumentPageUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    page_no: Optional[int] = None
    image_url: Optional[str] = None


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
    """
    생성은 보통 서버(ingestion)에서만 함.
    - general: chunk_level='child', parent_chunk_id=None, segment_index=1,
        chunk_index_in_segment=chunk_index(or 1 N)
    - parent_child:
      - parent row: chunk_level='parent', chunk_index=None, vector 없음
      - child row : chunk_level='child', parent_chunk_id=..., chunk_index not null, vector 있음
    """
    model_config = ConfigDict(from_attributes=False)

    knowledge_id: int
    page_id: Optional[int] = None

    chunk_level: ChunkLevel = "child"
    parent_chunk_id: Optional[int] = None

    segment_index: int = Field(default=1, ge=1)
    chunk_index_in_segment: Optional[int] = Field(default=None, ge=1)

    # 글로벌 인덱스: parent는 None, child는 필수
    chunk_index: Optional[int] = Field(default=None, ge=1)

    chunk_text: str
    created_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _validate(self):
        if self.chunk_level == "parent":
            if self.chunk_index is not None:
                raise ValueError("parent chunk must have chunk_index=None")
            if self.parent_chunk_id is not None:
                raise ValueError("parent chunk must have parent_chunk_id=None")
        else:
            if self.chunk_index is None:
                raise ValueError("child chunk must have chunk_index")
        return self


class DocumentChunkUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    page_id: Optional[int] = None
    # 인덱스/레벨/관계는 서버 로직에서만 관리하는 전제(수정 막는 게 안전)
    chunk_text: Optional[str] = None


class DocumentChunkResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: int
    knowledge_id: int
    page_id: Optional[int] = None

    chunk_level: str
    parent_chunk_id: Optional[int] = None

    segment_index: int
    chunk_index_in_segment: Optional[int] = None

    chunk_index: Optional[int] = None
    chunk_text: str
    created_at: datetime
    # vector_memory는 외부로 내보내지 않음
