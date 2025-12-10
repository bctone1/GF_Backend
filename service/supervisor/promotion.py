# service/supervisor/promotion.py
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.supervisor.core import PartnerPromotionRequest
from models.user.account import AppUser
from models.partner.partner_core import Partner
from crud.supervisor import core as sup_core
from crud.partner import partner_core as partner_crud
from crud.partner.partner_core import OrgConflict
from service.email import send_email, EmailSendError

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)

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
    - Org 결정 (요청에 org_id 있으면 사용, 없으면 org_name 기반 신규 생성)
    - Partner 엔터티 생성 (org_id + user_id)
    - user.users.partner_id 에 partner.id 세팅
    - user.default_role 을 partner 계열로 변경(예: 'partner')
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

    # 이미 파트너인 유저면 막기
    if user.partner_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_already_partner",
        )

    # 4) Org 결정
    org = None
    org_id = getattr(req, "org_id", None)

    if org_id is not None:
        org = partner_crud.get_org(db, org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="org_not_found_for_request",
            )
    else:
        # 요청에 org_id가 없으면 org_name 기반으로 Org 생성
        org_name = getattr(req, "org_name", None) or "Unnamed Org"
        org_code = getattr(req, "org_code", None) if hasattr(req, "org_code") else None

        try:
            org = partner_crud.create_org(
                db,
                name=org_name,
                code=org_code,
            )
        except OrgConflict:
            # code 충돌 시 기존 Org 재조회
            if org_code:
                org = partner_crud.get_org_by_code(db, org_code)
            else:
                # create_org 내부 slug 규칙과 최대한 맞춰서 재조회
                slug = partner_crud._slugify(org_name)  # 내부 helper지만 동일 파일 내이므로 사용
                org = partner_crud.get_org_by_code(db, slug)

        if not org:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="org_create_failed",
            )

    # 5) Partner 엔터티 생성
    phone = getattr(req, "phone_number", None) if hasattr(req, "phone_number") else None
    role = target_role or getattr(req, "target_role", "partner")

    full_name = (
        user.profile.full_name
        if getattr(user, "profile", None) and user.profile.full_name
        else user.email
    )

    partner = Partner(
        org_id=org.id,
        user_id=user.user_id,
        full_name=full_name,
        email=user.email,
        phone=phone,
        role=role,
        is_active=True,
    )
    db.add(partner)
    db.flush()  # partner.id 확보

    # 6) 유저에 partner_id 세팅 + 기본 역할 변경
    user.partner_id = partner.id
    user.default_role = role
    db.add(user)

    # 7) 요청 상태 업데이트 (승인)
    now = _utcnow()
    req.status = "approved"
    if hasattr(req, "decided_at"):
        req.decided_at = now

    # org_id / partner_id를 요청 레코드에 백필(backfill)하고 싶으면
    if hasattr(req, "org_id") and getattr(req, "org_id", None) is None:
        req.org_id = org.id
    if hasattr(req, "partner_id"):
        req.partner_id = partner.id

    db.add(req)
    db.commit()
    db.refresh(req)

    # 8) 승인 완료 후 이메일 발송 (실패해도 승인 롤백하지 않음)
    try:
        if user.email:
            subject = "[GrowFit] 강사 승인이 완료되었습니다."
            body = (
                f"{full_name}님,\n\n"
                "GrowFit 강사 신청이 승인되었습니다.\n"
                "이제 강의를 개설하고 학생을 초대할 수 있어요.\n\n"
                "로그인 후 강의 관리 화면에서 클래스를 만들어보세요.\n\n"
                "- GrowFit 운영팀 드림"
            )
            send_email(
                to_email=user.email,
                subject=subject,
                body=body,
                is_html=False,
            )
    except EmailSendError:
        # 이메일 때문에 비즈니스 로직을 깨뜨리면 안 되므로 로깅만
        logger.exception(
            "Failed to send partner approval email",
            extra={
                "promotion_request_id": request_id,
                "user_id": user.user_id,
                "partner_id": partner.id,
            },
        )

    return req


def reject_partner_request(
    db: Session,
    *,
    request_id: int,
) -> PartnerPromotionRequest:
    """
    파트너/강사 승격 요청 거절 서비스 로직.

    - pending 상태만 거절 가능
    - user.partner_id 는 건드리지 않음
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