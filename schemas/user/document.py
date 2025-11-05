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
    status: Optional[str] = None          # server default 'processing'
    chunk_count: Optional[int] = None     # server default 0
    uploaded_at: Optional[datetime] = None


class DocumentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    name: Optional[str] = None
    folder_path: Optional[str] = None
    status: Optional[str] = None
    chunk_count: Optional[int] = None
    # updated_at is server-managed; include only if you allow manual override
    # updated_at: Optional[datetime] = None


class DocumentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    document_id: int
    owner_id: int
    name: str
    file_format: str
    file_size_bytes: int
    folder_path: Optional[str] = None
    status: str
    chunk_count: int
    uploaded_at: datetime
    updated_at: datetime


# =========================================================
# user.document_processing_jobs
# =========================================================
class DocumentProcessingJobCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    document_id: int
    stage: str
    status: Optional[str] = None          # server default 'queued'
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DocumentProcessingJobUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    stage: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DocumentProcessingJobResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    job_id: int
    document_id: int
    stage: str
    status: str
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# =========================================================
# user.document_tags
# =========================================================
class DocumentTagCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    name: str


class DocumentTagUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    name: Optional[str] = None


class DocumentTagResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    tag_id: int
    name: str


# =========================================================
# user.document_tag_assignments
# =========================================================
class DocumentTagAssignmentCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    document_id: int
    tag_id: int


class DocumentTagAssignmentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    # no updatable fields at the moment
    pass


class DocumentTagAssignmentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    assignment_id: int
    document_id: int
    tag_id: int


# =========================================================
# user.document_usage
# =========================================================
class DocumentUsageCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    document_id: int
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
    document_id: int
    user_id: Optional[int] = None
    usage_type: str
    usage_count: int
    last_used_at: datetime
