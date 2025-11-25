# service/supervisor/promotion.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.supervisor.core import PartnerPromotionRequest
from models.user.account import AppUser
from crud.supervisor import core as sup_core
from crud.supervisor.core import (
    PromotionNotFound,
    _promote_user_to_partner_internal,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==============================
# 조회 계열 (crud 위임)
# ==============================
def get_promotion_request(
    db: Session,
    *,
    request_id: int,
) -> PartnerPromotionRequest:
    req = sup_core.get_promotion_request(db, request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="promotion_request_not_found",
        )
    return req


def list_promotion_requests(
    db: Session,
    *,
    status: Optional[str] = None,
) -> Sequence[PartnerPromotionRequest]:
    """
    status 필터만 얹어서 단순 조회
    """
    return sup_core.list_promotion_requests(db, status=status)


# ==============================
# 승인 / 거절 비즈니스 로직
# ==============================
def approve_partner_request(
    db: Session,
    *,
    request_id: int,
    target_role: str | None = None,
) -> PartnerPromotionRequest:
    """
    파트너/강사 승격 요청 승인 서비스 로직.

    - pending 상태만 승인 가능
    - user.users.is_partner = True 로 플래그 설정
    - Org / PartnerUser 생성(or 재사용)
    - PartnerPromotionRequest 상태 업데이트
    """
    # 1) 요청 조회
    req = sup_core.get_promotion_request(db, request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="promotion_request_not_found",
        )

    # 2) 상태 검증
    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"promotion_request_already_{req.status}",
        )

    # 3) 유저 조회
    user = db.get(AppUser, req.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found_for_request",
        )

    # 4) is_partner 플래그 보장 (멱등)
    if not getattr(user, "is_partner", False):
        user.is_partner = True
        db.add(user)

    # 5) Org / PartnerUser 생성 또는 재사용
    try:
        org, partner_user = _promote_user_to_partner_internal(
            db=db,
            email=user.email,              # 실제 AppUser 기준
            partner_name=req.org_name,     # 요청 폼에서 받은 기관명
            created_by=None,               # 별도 supervisor 유저 없으니 None
            partner_user_role=target_role or req.target_role,
        )
    except PromotionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found_for_partner",
        )

    # 6) 요청 상태 업데이트 (여기가 지금 빠져 있었음)
    now = _utcnow()
    req.status = "approved"
    if hasattr(req, "decided_at"):
        req.decided_at = now

    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def reject_partner_request(
    db: Session,
    *,
    request_id: int,
) -> PartnerPromotionRequest:
    """
    파트너/강사 승격 요청 거절 서비스 로직.

    - pending 상태만 거절 가능
    - is_partner 플래그는 건드리지 않음
    """
    req = sup_core.get_promotion_request(db, request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="promotion_request_not_found",
        )

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"promotion_request_already_{req.status}",
        )

    now = _utcnow()
    req.status = "rejected"
    if hasattr(req, "decided_at"):
        req.decided_at = now

    db.add(req)
    db.commit()
    db.refresh(req)
    return req
