# schemas/partner/activity.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from schemas.base import ORMBase


class ActivityEventResponse(ORMBase):
    """활동 이벤트 응답 스키마."""

    id: int
    partner_id: int
    class_id: Optional[int] = None
    student_id: Optional[int] = None
    event_type: str
    title: str
    description: Optional[str] = None
    meta: Dict[str, Any] = {}
    created_at: datetime
