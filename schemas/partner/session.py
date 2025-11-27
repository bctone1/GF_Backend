from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, List

from pydantic import ConfigDict

from schemas.base import ORMBase, MoneyBase, Page
from schemas.enums import (
    SessionMode,        # 'single' | 'parallel'
    SessionStatus,      # 'active' | 'completed' | 'canceled' | 'error'
    SessionMessageType, # 'text' | 'image' | 'audio' | 'file' | 'tool'
    SenderType,         # 'student' | 'partner' | 'system'
)


# ==============================
# ai_sessions
# ==============================
class AiSessionCreate(ORMBase):
    student_id: Optional[int] = None
    class_id: Optional[int] = None
    mode: SessionMode
    model_name: str
    status: Optional[SessionStatus] = None              # DB default 'active'
    started_at: Optional[datetime] = None               # 서버 채움 권장
    ended_at: Optional[datetime] = None
    total_messages: Optional[int] = None                # DB default 0
    total_tokens: Optional[int] = None                  # DB default 0
    total_cost: Optional[Decimal] = None                # DB default 0
    initiated_by: Optional[int] = None


class AiSessionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    student_id: Optional[int] = None
    class_id: Optional[int] = None
    mode: Optional[SessionMode] = None
    model_name: Optional[str] = None
    status: Optional[SessionStatus] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_messages: Optional[int] = None
    total_tokens: Optional[int] = None
    total_cost: Optional[Decimal] = None
    initiated_by: Optional[int] = None


class AiSessionResponse(MoneyBase):
    id: int
    student_id: Optional[int] = None
    class_id: Optional[int] = None
    mode: SessionMode
    model_name: str
    status: SessionStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_messages: int
    total_tokens: int
    total_cost: Decimal
    initiated_by: Optional[int] = None
    # 일단 다 불러오고, 필요 없는 기능 추후 제거
    messages: Optional[List["SessionMessageResponse"]] = None  # noqa: F821


AiSessionPage = Page[AiSessionResponse]


# ==============================
# session_messages
# ==============================
class SessionMessageCreate(ORMBase):
    session_id: int
    sender_type: SenderType          # 'student' | 'partner' | 'system'
    sender_id: Optional[int] = None
    message_type: SessionMessageType = "text"  # DB default 'text'
    content: str
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    meta: Optional[dict[str, Any]] = None
    # content_vector는 응답 비노출. 입력도 일반적으로 받지 않음.


class SessionMessageUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    sender_type: Optional[SenderType] = None
    sender_id: Optional[int] = None
    message_type: Optional[SessionMessageType] = None
    content: Optional[str] = None
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    meta: Optional[dict[str, Any]] = None


class SessionMessageResponse(ORMBase):
    id: int
    session_id: int
    sender_type: SenderType
    sender_id: Optional[int] = None
    message_type: SessionMessageType
    content: str
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    meta: Optional[dict[str, Any]] = None
    created_at: datetime


SessionMessagePage = Page[SessionMessageResponse]
