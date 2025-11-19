# app/endpoints/user/promotion.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from crud.user import promotion as promotion_crud
from schemas.user.promotion import (
    PartnerPromotionRequestCreate,
    PartnerPromotionRequestResponse,
)

router = APIRouter()


# ==============================
# 내 강사/파트너 승격 요청 생성
# ==============================
@router.post(
    "/promotions/partner",
    response_model=PartnerPromotionRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_partner_promotion_request(
    data: PartnerPromotionRequestCreate,
    db: Session = Depends(get_db),
    me=Depends(get_current_user),
):
    """
    로그인한 유저가 강사/파트너 승격을 신청
    - user.partner_promotion_requests 에 pending 1건 생성
    """
    full_name = getattr(me, "full_name", None)
    try:
        obj = promotion_crud.create_request(
            db,
            user_id=me.user_id,
            email=me.email,
            full_name=full_name,
            requested_org_name=data.requested_org_name,
            target_role=data.target_role,
            metadata=data.metadata,
        )
        return obj
    except promotion_crud.PromotionConflict as e:
        # 이미 pending 요청이 있을 때
        raise HTTPException(status_code=409, detail=str(e))


# ==============================
# 내 승격 요청 조회 (최신 1건)
# ==============================
@router.get(
    "/promotions/partner/me",
    response_model=PartnerPromotionRequestResponse,
)
def get_my_partner_promotion_request(
    db: Session = Depends(get_db),
    me=Depends(get_current_user),
):
    """
    내가 넣어둔 승격 요청 중 가장 최신 1건 조회
    (pending/approved/rejected 상관없이 최신)
    """
    obj = promotion_crud.get_my_latest_request(db, user_id=me.user_id)
    if not obj:
        raise HTTPException(status_code=404, detail="promotion request not found")
    return obj


# ==============================
# 내 승격 요청 취소
# ==============================
@router.post(
    "/promotions/partner/{request_id}/cancel",
    response_model=PartnerPromotionRequestResponse,
)
def cancel_my_partner_promotion_request(
    request_id: int,
    db: Session = Depends(get_db),
    me=Depends(get_current_user),
):
    """
    내가 넣어둔 pending 상태 승격 요청 취소
    """
    try:
        obj = promotion_crud.cancel_request(
            db,
            request_id=request_id,
            user_id=me.user_id,
        )
        return obj
    except promotion_crud.PromotionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except promotion_crud.PromotionConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
