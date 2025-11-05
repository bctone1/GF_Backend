# schemas/partner/session.py
from __future__ import annotations
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from schemas.base import ORMBase, MoneyBase


# ========== partner.ai_sessions ==========
class AiSessionCreate(MoneyBase):
    project_id: int
    student_id: Optional[int] = None
    mode: str                          # 'single' | 'parallel'
    model_name: str
    status: Optional[str] = None       # DB default 'active'
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_messages: Optional[int] = 0
    total_tokens: Optional[int] = 0
    total_cost: Optional[Decimal] = Decimal("0")
    initiated_by: Optional[int] = None


class AiSessionUpdate(MoneyBase):
    student_id: Optional[int] = None
    mode: Optional[str] = None
    model_name: Optional[str] = None
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_messages: Optional[int] = None
    total_tokens: Optional[int] = None
    total_cost: Optional[Decimal] = None
    initiated_by: Optional[int] = None


class AiSessionResponse(MoneyBase):
    id: int
    project_id: int
    student_id: Optional[int] = None
    mode: str
    model_name: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_messages: int
    total_tokens: int
    total_cost: Decimal
    initiated_by: Optional[int] = None


# ========== partner.session_messages ==========
class SessionMessageCreate(ORMBase):
    session_id: int
    sender_type: str                    # 'student' | 'staff' | 'system'
    sender_id: Optional[int] = None
    message_type: str = "text"
    content: str
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    # 벡터는 응답·내부용. 생성 시 필요하면 허용.
    content_vector: Optional[List[float]] = None


class SessionMessageUpdate(ORMBase):
    sender_type: Optional[str] = None
    sender_id: Optional[int] = None
    message_type: Optional[str] = None
    content: Optional[str] = None
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    content_vector: Optional[List[float]] = None


class SessionMessageResponse(ORMBase):
    id: int
    session_id: int
    sender_type: str
    sender_id: Optional[int] = None
    message_type: str
    content: str
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    content_vector: Optional[List[float]] = None
    created_at: datetime
