# schemas/user/document.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import ConfigDict

from schemas.base import ORMBase


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
# user.document_pages  (models.user.DocumentPage 대응)
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
# user.document_chunks  (models.user.DocumentChunk 대응)
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
    # vector_memory를 갱신하는 경우가 특별히 필요하면 여기 추가 가능


class DocumentChunkResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    chunk_id: int
    knowledge_id: int
    page_id: Optional[int] = None
    chunk_index: int
    chunk_text: str
    created_at: datetime
    # vector_memory는 보통 외부로 내보내지 않음
