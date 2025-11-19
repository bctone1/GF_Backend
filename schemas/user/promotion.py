# schemas/user/promotion.py
from __future__ import annotations

from typing import Any, Optional, Literal
from datetime import datetime

from pydantic import EmailStr, Field

from schemas.base import ORMBase


# 상태 타입 (필요하면 나중에 schemas.enums 로 분리)
PromotionStatus = Literal["pending", "approved", "rejected", "cancelled"]


# =========================
# Create
# =========================
class PartnerPromotionRequestCreate(ORMBase):
    """
    유저가 승격 요청 생성할 때 사용하는 입력 값
    - user_id, email, full_name, status, requested_at 등은 서버에서 채움
    """

    requested_org_name: str
    target_role: str = "partner_admin"
    meta: dict[str, Any] = Field(default_factory=dict)


# =========================
# Update (서버 내부/슈퍼바이저 처리용)
# =========================
class PartnerPromotionRequestUpdate(ORMBase):
    """
    승격 요청 상태/결과 갱신용
    - supervisor 쪽 승인/거절, 시스템 내부 처리 등에 사용
    """

    status: Optional[PromotionStatus] = None
    decided_reason: Optional[str] = None
    decided_at: Optional[datetime] = None
    partner_id: Optional[int] = None
    partner_user_id: Optional[int] = None
    target_role: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


# =========================
# Response
# =========================
class PartnerPromotionRequestResponse(ORMBase):
    """
    목록/단건 조회 응답용
    models.user.promotion.PartnerPromotionRequest 와 1:1 매핑
    """

    request_id: int
    user_id: int
    email: EmailStr
    full_name: Optional[str] = None

    requested_org_name: str
    target_role: str

    status: PromotionStatus
    requested_at: datetime
    decided_at: Optional[datetime] = None
    decided_reason: Optional[str] = None

    partner_id: Optional[int] = None
    partner_user_id: Optional[int] = None

    meta: dict[str, Any]
