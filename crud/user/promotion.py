# crud/user/promotion.py
from __future__ import annotations

from typing import Optional, Sequence, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user.promotion import PartnerPromotionRequest


# ==============================
# helpers / exceptions
# ==============================
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PromotionError(Exception):
    ...


class PromotionNotFound(PromotionError):
    ...


class PromotionConflict(PromotionError):
    """
    이미 처리된 요청이거나, pending 요청이 중복되는 경우 등
    """
    ...


# ==============================
# Create (user → 승격 요청 생성)
# ==============================
def create_request(
    db: Session,
    *,
    user_id: int,
    email: str,
    full_name: Optional[str],
    requested_org_name: str,
    target_role: str = "partner_admin",
    meta: Optional[Dict[str, Any]] = None,
) -> PartnerPromotionRequest:
    """
    유저가 '파트너/강사 승격' 요청을 새로 생성
    - user_id 당 pending 상태는 1개만 허용 (테이블 수준 인덱스 + 여기서도 체크)
    """

    # 이미 pending 요청이 있는지 체크 (멱등/제약용)
    existing = db.execute(
        select(PartnerPromotionRequest).where(
            PartnerPromotionRequest.user_id == user_id,
            PartnerPromotionRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if existing:
        raise PromotionConflict("pending promotion request already exists for this user")

    obj = PartnerPromotionRequest(
        user_id=user_id,
        email=email,
        full_name=full_name,
        requested_org_name=requested_org_name,
        target_role=target_role or "partner_admin",
        status="pending",
        meta=meta or {},
        requested_at=_utcnow(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ==============================
# Read
# ==============================
def get_request(
    db: Session,
    request_id: int,
) -> Optional[PartnerPromotionRequest]:
    """
    request_id 기준 단건 조회
    """
    return db.get(PartnerPromotionRequest, request_id)


def get_my_latest_request(
    db: Session,
    *,
    user_id: int,
) -> Optional[PartnerPromotionRequest]:
    """
    특정 유저의 승격 요청 중 가장 최근 것 1건
    (pending / approved / rejected 상관 없이 최신)
    """
    stmt = (
        select(PartnerPromotionRequest)
        .where(PartnerPromotionRequest.user_id == user_id)
        .order_by(PartnerPromotionRequest.requested_at.desc())
    )
    return db.execute(stmt).scalars().first()


def get_my_pending_request(
    db: Session,
    *,
    user_id: int,
) -> Optional[PartnerPromotionRequest]:
    """
    특정 유저의 pending 상태 요청 1건 (있을 수도, 없을 수도 있음)
    """
    stmt = select(PartnerPromotionRequest).where(
        PartnerPromotionRequest.user_id == user_id,
        PartnerPromotionRequest.status == "pending",
    )
    return db.execute(stmt).scalar_one_or_none()


def list_requests(
    db: Session,
    *,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Sequence[PartnerPromotionRequest]:
    """
    supervisor / 내부 용도: 전체/필터 조회
    - status: pending / approved / rejected / cancelled
    - user_id: 특정 유저만 필터링
    """
    stmt = select(PartnerPromotionRequest).order_by(
        PartnerPromotionRequest.requested_at.desc()
    )
    if status:
        stmt = stmt.where(PartnerPromotionRequest.status == status)
    if user_id is not None:
        stmt = stmt.where(PartnerPromotionRequest.user_id == user_id)

    return db.execute(stmt).scalars().all()


# ==============================
# Update: 승인 / 거절 (상태 변경 전용)
# ==============================
def approve_request(
    db: Session,
    *,
    request_id: int,
    decided_reason: Optional[str] = None,
    partner_id: Optional[int] = None,
    partner_user_id: Optional[int] = None,
    target_role: Optional[str] = None,
) -> PartnerPromotionRequest:
    """
    승격 요청 승인 처리
    - 상태가 pending 인 경우에만 승인 가능
    - partner_id / partner_user_id 는 이미 생성된 객체의 FK를 받아서 기록
      (실제 파트너/강사 생성 로직은 service/supervisor 레이어에서 처리)
    """
    obj = db.get(PartnerPromotionRequest, request_id)
    if not obj:
        raise PromotionNotFound(f"promotion request not found: id={request_id}")
    if obj.status != "pending":
        raise PromotionConflict(f"promotion request already {obj.status}")

    obj.status = "approved"
    obj.decided_at = _utcnow()
    obj.decided_reason = decided_reason
    if partner_id is not None:
        obj.partner_id = partner_id
    if partner_user_id is not None:
        obj.partner_user_id = partner_user_id
    if target_role is not None:
        obj.target_role = target_role

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def reject_request(
    db: Session,
    *,
    request_id: int,
    decided_reason: Optional[str] = None,
) -> PartnerPromotionRequest:
    """
    승격 요청 거절 처리
    - 상태가 pending 인 경우에만 거절 가능
    """
    obj = db.get(PartnerPromotionRequest, request_id)
    if not obj:
        raise PromotionNotFound(f"promotion request not found: id={request_id}")
    if obj.status != "pending":
        raise PromotionConflict(f"promotion request already {obj.status}")

    obj.status = "rejected"
    obj.decided_at = _utcnow()
    obj.decided_reason = decided_reason

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def cancel_request(
    db: Session,
    *,
    request_id: int,
    user_id: int,
) -> PartnerPromotionRequest:
    """
    유저가 스스로 취소하는 용도 (선택)
    - 본인 요청 + pending 상태만 취소 가능
    """
    obj = db.get(PartnerPromotionRequest, request_id)
    if not obj or obj.user_id != user_id:
        raise PromotionNotFound("promotion request not found for this user")
    if obj.status != "pending":
        raise PromotionConflict(f"promotion request already {obj.status}")

    obj.status = "cancelled"
    obj.decided_at = _utcnow()

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
