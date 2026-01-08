# schemas/user/document.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, List, Literal

from pydantic import ConfigDict, Field, model_validator

from schemas.base import ORMBase
from core import config


# =========================================================
# Defaults from core.config (Single Source of Truth)
# =========================================================
_DI: dict[str, Any] = dict(getattr(config, "DEFAULT_INGESTION", {}) or {})
_DS: dict[str, Any] = dict(getattr(config, "DEFAULT_SEARCH", {}) or {})


def _di(key: str, default: Any) -> Any:
    return _DI.get(key, default)


def _ds(key: str, default: Any) -> Any:
    return _DS.get(key, default)


# =========================================================
# Types (정합성 고정)
# =========================================================
EmbeddingDim = Literal[1536]
ScoreType = Literal["cosine_similarity"]

ChunkStrategy = Literal["recursive", "token", "semantic"]
ChunkingMode = Literal["general", "parent_child"]
ChunkLevel = Literal["child", "parent"]


# =========================================================
# json_schema_extra helpers (examples from config)
# =========================================================
def _ingestion_general_example() -> dict[str, Any]:
    return {
        "knowledge_id": 123,
        "chunk_size": int(_di("chunk_size", 600)),
        "chunk_overlap": int(_di("chunk_overlap", 200)),
        "max_chunks": int(_di("max_chunks", 100)),
        "chunk_strategy": str(_di("chunk_strategy", "recursive")),
        "chunking_mode": "general",
        "embedding_provider": str(_di("embedding_provider", "openai")),
        "embedding_model": str(_di("embedding_model", "text-embedding-3-small")),
        "embedding_dim": int(getattr(config, "EMBEDDING_DIM_FIXED", 1536)),
        "extra": {},
    }


def _ingestion_parent_child_example() -> dict[str, Any]:
    return {
        "knowledge_id": 123,
        "chunk_size": int(_di("chunk_size", 600)),
        "chunk_overlap": int(_di("chunk_overlap", 200)),
        "max_chunks": int(_di("max_chunks", 100)),
        "chunk_strategy": str(_di("chunk_strategy", "recursive")),
        "chunking_mode": "parent_child",
        "segment_separator": str(_di("segment_separator", "\n\n")),
        "parent_chunk_size": int(_di("parent_chunk_size", 1500)),
        "parent_chunk_overlap": int(_di("parent_chunk_overlap", 400)),
        "embedding_provider": str(_di("embedding_provider", "openai")),
        "embedding_model": str(_di("embedding_model", "text-embedding-3-small")),
        "embedding_dim": int(getattr(config, "EMBEDDING_DIM_FIXED", 1536)),
        "extra": {},
    }


def _inject_ingestion_create_examples(schema: dict[str, Any]) -> None:
    schema.setdefault("examples", [_ingestion_general_example(), _ingestion_parent_child_example()])


def _inject_ingestion_update_examples(schema: dict[str, Any]) -> None:
    schema.setdefault(
        "examples",
        [
            {
                "chunking_mode": "general",
                "chunk_size": int(_di("chunk_size", 600)),
                "chunk_overlap": int(_di("chunk_overlap", 200)),
                "max_chunks": int(_di("max_chunks", 100)),
                "chunk_strategy": str(_di("chunk_strategy", "recursive")),
            },
            {
                "chunking_mode": "parent_child",
                "segment_separator": str(_di("segment_separator", "\n\n")),
                "parent_chunk_size": int(_di("parent_chunk_size", 1500)),
                "parent_chunk_overlap": int(_di("parent_chunk_overlap", 400)),
                "chunk_size": int(_di("chunk_size", 600)),
                "chunk_overlap": int(_di("chunk_overlap", 200)),
                "max_chunks": int(_di("max_chunks", 100)),
                "chunk_strategy": str(_di("chunk_strategy", "recursive")),
            },
        ],
    )


def _search_example() -> dict[str, Any]:
    return {
        "knowledge_id": 123,
        "top_k": int(_ds("top_k", 8)),
        "min_score": str(_ds("min_score", "0.20")),  # Decimal은 문자열이 Swagger에서 안전
        "score_type": str(getattr(config, "KB_SCORE_TYPE_FIXED", "cosine_similarity")),
        "reranker_enabled": bool(_ds("reranker_enabled", False)),
        "reranker_model": _ds("reranker_model", None),
        "reranker_top_n": int(_ds("reranker_top_n", 5)),
    }


def _inject_search_create_examples(schema: dict[str, Any]) -> None:
    schema.setdefault("examples", [_search_example()])


def _inject_search_update_examples(schema: dict[str, Any]) -> None:
    schema.setdefault(
        "examples",
        [
            {
                "top_k": int(_ds("top_k", 8)),
                "min_score": str(_ds("min_score", "0.20")),
                "reranker_enabled": bool(_ds("reranker_enabled", False)),
                "reranker_model": _ds("reranker_model", None),
                "reranker_top_n": int(_ds("reranker_top_n", 5)),
            }
        ],
    )


def _inject_preview_examples(schema: dict[str, Any]) -> None:
    schema.setdefault(
        "examples",
        [
            {
                "chunk_size": int(_di("chunk_size", 600)),
                "chunk_overlap": int(_di("chunk_overlap", 200)),
                "max_chunks": int(_di("max_chunks", 100)),
                "chunk_strategy": str(_di("chunk_strategy", "recursive")),
                "chunking_mode": "general",
            },
            {
                "chunk_size": int(_di("chunk_size", 600)),
                "chunk_overlap": int(_di("chunk_overlap", 200)),
                "max_chunks": int(_di("max_chunks", 100)),
                "chunk_strategy": str(_di("chunk_strategy", "recursive")),
                "chunking_mode": "parent_child",
                "segment_separator": str(_di("segment_separator", "\n\n")),
                "parent_chunk_size": int(_di("parent_chunk_size", 1500)),
                "parent_chunk_overlap": int(_di("parent_chunk_overlap", 400)),
            },
        ],
    )


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

    status: Optional[str] = None
    chunk_count: Optional[int] = None
    progress: Optional[int] = None
    error_message: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class DocumentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    name: Optional[str] = None
    folder_path: Optional[str] = None
    status: Optional[str] = None
    chunk_count: Optional[int] = None
    progress: Optional[int] = None
    error_message: Optional[str] = None


class DocumentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    knowledge_id: int
    owner_id: int
    name: str
    file_format: str
    file_size_bytes: int
    folder_path: Optional[str] = None

    status: str
    chunk_count: int
    progress: int
    error_message: Optional[str] = None

    uploaded_at: datetime
    updated_at: datetime


# =========================================================
# user.document_ingestion_settings
# =========================================================
class DocumentIngestionSettingCreate(ORMBase):
    model_config = ConfigDict(
        from_attributes=False,
        json_schema_extra=_inject_ingestion_create_examples,
    )

    knowledge_id: int

    # child chunking
    chunk_size: int = Field(default=int(_di("chunk_size", 600)), ge=1)
    chunk_overlap: int = Field(default=int(_di("chunk_overlap", 200)), ge=0)
    max_chunks: int = Field(default=int(_di("max_chunks", 100)), ge=1)
    chunk_strategy: ChunkStrategy = Field(default=str(_di("chunk_strategy", "recursive")))

    # mode
    chunking_mode: ChunkingMode = Field(default=str(_di("chunking_mode", "general")))
    segment_separator: Optional[str] = Field(default=None, min_length=1, max_length=64)

    # parent chunking (parent_child에서만 의미)
    parent_chunk_size: Optional[int] = Field(default=None, ge=1)
    parent_chunk_overlap: Optional[int] = Field(default=None, ge=0)

    # embedding
    embedding_provider: str = Field(default=str(_di("embedding_provider", "openai")))
    embedding_model: str = Field(default=str(_di("embedding_model", "text-embedding-3-small")))
    embedding_dim: EmbeddingDim = Field(default=int(getattr(config, "EMBEDDING_DIM_FIXED", 1536)))

    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_overlap_and_mode(self):
        if self.chunk_strategy != "recursive":
            raise ValueError("unsupported chunk_strategy (MVP): only 'recursive' is allowed")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")

        if self.chunking_mode == "parent_child":
            if self.segment_separator is None:
                self.segment_separator = str(_di("segment_separator", "\n\n"))

            # parent 기본값 주입(없으면 프리뷰에서 parent가 1개로만 뭉칠 수 있음)
            if self.parent_chunk_size is None:
                self.parent_chunk_size = int(_di("parent_chunk_size", 1500))
            if self.parent_chunk_overlap is None:
                self.parent_chunk_overlap = int(_di("parent_chunk_overlap", 400))

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


class DocumentIngestionSettingUpdate(ORMBase):
    model_config = ConfigDict(
        from_attributes=False,
        json_schema_extra=_inject_ingestion_update_examples,
    )

    chunk_size: Optional[int] = Field(default=None, ge=1)
    chunk_overlap: Optional[int] = Field(default=None, ge=0)
    max_chunks: Optional[int] = Field(default=None, ge=1)
    chunk_strategy: Optional[ChunkStrategy] = None

    chunking_mode: Optional[ChunkingMode] = None
    segment_separator: Optional[str] = Field(default=None, min_length=1, max_length=64)

    parent_chunk_size: Optional[int] = Field(default=None, ge=1)
    parent_chunk_overlap: Optional[int] = Field(default=None, ge=0)

    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dim: Optional[EmbeddingDim] = None
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

        if self.chunking_mode == "general":
            self.segment_separator = None
            self.parent_chunk_size = None
            self.parent_chunk_overlap = None

        if self.chunking_mode == "parent_child":
            if "segment_separator" in self.model_fields_set and self.segment_separator is None:
                raise ValueError("segment_separator cannot be null when chunking_mode='parent_child'")

            # 프리뷰/단독 사용 시 안전장치(필드셋엔 안 들어가서 patch payload에는 보통 안 섞임)
            if "segment_separator" not in self.model_fields_set and self.segment_separator is None:
                self.segment_separator = str(_di("segment_separator", "\n\n"))

        return self


class DocumentIngestionSettingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    knowledge_id: int

    chunk_size: int
    chunk_overlap: int
    max_chunks: int
    chunk_strategy: ChunkStrategy

    chunking_mode: ChunkingMode
    segment_separator: Optional[str] = None
    parent_chunk_size: Optional[int] = None
    parent_chunk_overlap: Optional[int] = None

    embedding_provider: str
    embedding_model: str
    embedding_dim: EmbeddingDim

    extra: dict[str, Any]

    created_at: datetime
    updated_at: datetime


# =========================================================
# user.document_search_settings
# =========================================================
class DocumentSearchSettingCreate(ORMBase):
    model_config = ConfigDict(
        from_attributes=False,
        json_schema_extra=_inject_search_create_examples,
    )

    knowledge_id: int

    top_k: int = Field(default=int(_ds("top_k", 8)), ge=1)

    min_score: Decimal = Field(
        default=Decimal(str(_ds("min_score", "0.20"))),
        ge=Decimal("0"),
        le=Decimal("1"),
    )

    score_type: ScoreType = Field(default=str(getattr(config, "KB_SCORE_TYPE_FIXED", "cosine_similarity")))

    reranker_enabled: bool = Field(default=bool(_ds("reranker_enabled", False)))
    reranker_model: Optional[str] = Field(default=_ds("reranker_model", None))
    reranker_top_n: int = Field(default=int(_ds("reranker_top_n", 5)), ge=1)

    @model_validator(mode="after")
    def _validate_reranker_top_n(self):
        if self.reranker_top_n > self.top_k:
            raise ValueError("reranker_top_n must be <= top_k")
        return self


class DocumentSearchSettingUpdate(ORMBase):
    model_config = ConfigDict(
        from_attributes=False,
        json_schema_extra=_inject_search_update_examples,
    )

    top_k: Optional[int] = Field(default=None, ge=1)
    min_score: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("1"))

    score_type: Optional[ScoreType] = None

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
        json_schema_extra=_inject_preview_examples,
    )

    chunk_size: int = Field(default=int(_di("chunk_size", 600)), ge=1)
    chunk_overlap: int = Field(default=int(_di("chunk_overlap", 200)), ge=0)
    max_chunks: int = Field(default=int(_di("max_chunks", 100)), ge=1)
    chunk_strategy: ChunkStrategy = Field(default=str(_di("chunk_strategy", "recursive")))

    chunking_mode: ChunkingMode = Field(default=str(_di("chunking_mode", "general")))
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
                self.segment_separator = str(_di("segment_separator", "\n\n"))

            if self.parent_chunk_size is None:
                self.parent_chunk_size = int(_di("parent_chunk_size", 1500))
            if self.parent_chunk_overlap is None:
                self.parent_chunk_overlap = int(_di("parent_chunk_overlap", 400))

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
    usage_count: Optional[int] = None
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
    page_no: Optional[int] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None


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
    - general: chunk_level='child', parent_chunk_id=None, segment_index=1
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

    chunk_index: Optional[int] = Field(default=None, ge=1)  # parent는 None, child는 필수
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
