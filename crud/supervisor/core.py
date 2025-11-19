# crud/supervisor/core.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from datetime import datetime, timezone
import random
import string

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.supervisor.core import (
    Plan,
    Organization,
    SupervisorUser as SupUser,
    UserRole,
    UserRoleAssignment,
    Session as SupSession,
    PartnerPromotionRequest,
)
# user tier 가입 사용자
from models.user.account import AppUser  # table: user.users (PK: user_id, email)
# partner tier
from models.partner.partner_core import Partner, PartnerUser  # partners, partner_users


# ==============================
# helpers
# ==============================
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _gen_code(prefix: str = "PT", length: int = 6) -> str:
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{body}"

def _slugify_code(name: str, max_len: int = 12) -> str:
    base = "".join(ch for ch in name.upper() if ch.isalnum())
    base = base[: max_len] or "PARTNER"
    return base


# ==============================
# Supervisor Users
# ==============================
def create_supervisor_user(
    db: Session,
    *,
    org_id: int,
    email: str,
    name: str,
    role: str = "supervisor_admin",
    status: str = "active",
) -> SupUser:
    sup = SupUser(
        organization_id=org_id,
        email=email,
        name=name,
        role=role,
        status=status,
        signup_at=_utcnow(),
    )
    db.add(sup)
    db.commit()
    db.refresh(sup)
    return sup


def get_supervisor_user_by_email(db: Session, *, email: str) -> Optional[SupUser]:
    stmt = select(SupUser).where(func.lower(SupUser.email) == func.lower(email))
    return db.execute(stmt).scalar_one_or_none()


# ==============================
# Roles
# ==============================
def get_or_create_role(
    db: Session,
    *,
    role_name: str,
    permissions: Optional[dict] = None,
) -> UserRole:
    stmt = select(UserRole).where(UserRole.role_name == role_name)
    role = db.execute(stmt).scalar_one_or_none()
    if role:
        return role
    role = UserRole(role_name=role_name, permissions_json=permissions or {})
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def assign_role(
    db: Session,
    *,
    user_id: int,
    role_name: str,
    assigned_by: Optional[int] = None,
) -> UserRoleAssignment:
    role = get_or_create_role(db, role_name=role_name)
    # 멱등: 이미 있으면 리턴
    stmt = select(UserRoleAssignment).where(
        UserRoleAssignment.user_id == user_id,
        UserRoleAssignment.role_id == role.role_id,
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        return existing
    ura = UserRoleAssignment(
        user_id=user_id,
        role_id=role.role_id,
        assigned_by=assigned_by,
    )
    db.add(ura)
    db.commit()
    db.refresh(ura)
    return ura


# ==============================
# Promotion: PartnerPromotionRequest 기반 승격
# ==============================
class PromotionError(Exception):
    ...


class PromotionNotFound(PromotionError):
    ...


class PromotionConflict(PromotionError):
    """
    이미 처리된 요청 등을 다시 처리하려 할 때 사용
    """
    ...


def _promote_user_to_partner_internal(
    db: Session,
    *,
    email: str,
    partner_name: str,
    created_by: Optional[int] = None,
    partner_user_role: str = "partner_admin",
) -> Tuple[Partner, PartnerUser]:
    """
    실제 partners / partner_users 를 만드는 하위 유틸.

    - 기존 promote_user_to_partner 로직을 내부용으로 옮긴 것
    - 승격 요청(PartnerPromotionRequest) 승인에서만 호출하는 걸 권장
    """
    # 1) 가입 사용자 확인 (user.users)
    app_user = db.execute(
        select(AppUser).where(func.lower(AppUser.email) == func.lower(email))
    ).scalar_one_or_none()
    if not app_user:
        raise PromotionNotFound(f"no user.users found for email={email}")

    # 2) 파트너 코드/이름 정리 (코드는 내부에서 자동 생성)
    base_code = _slugify_code(partner_name)[:16]

    # 3) 멱등: 동일 code 파트너가 있으면 재사용
    partner = db.execute(
        select(Partner).where(Partner.code == base_code)
    ).scalar_one_or_none()
    if not partner:
        try_code = base_code
        tries = 0
        while True:
            try:
                partner = Partner(
                    name=partner_name,
                    code=try_code,
                    status="active",
                    created_by=created_by,
                )
                db.add(partner)
                db.flush()  # PK 확보
                break
            except IntegrityError:
                db.rollback()
                tries += 1
                if tries > 3:
                    # 최종 백오프: 랜덤 코드
                    try_code = _gen_code(
                        prefix=_slugify_code(partner_name)[:4],
                        length=6,
                    )
                else:
                    try_code = f"{base_code}{tries}"

    # 4) 멱등: 이미 partner_users 매핑이 있으면 그대로 반환
    pu = db.execute(
        select(PartnerUser).where(
            PartnerUser.partner_id == partner.id,
            PartnerUser.user_id == app_user.user_id,
        )
    ).scalar_one_or_none()
    if not pu:
        pu = PartnerUser(
            partner_id=partner.id,
            user_id=app_user.user_id,
            full_name=getattr(app_user, "full_name", None)
            or getattr(app_user, "name", None)
            or email,
            email=app_user.email,
            role=partner_user_role,
            is_active=True,
        )
        db.add(pu)

    db.commit()
    db.refresh(partner)
    db.refresh(pu)
    return partner, pu


# ----- 승격 요청 조회/승인/거절 -----
def get_promotion_request(
    db: Session,
    request_id: int,
) -> Optional[PartnerPromotionRequest]:
    return db.get(PartnerPromotionRequest, request_id)


def list_promotion_requests(
    db: Session,
    *,
    status: Optional[str] = None,
) -> Sequence[PartnerPromotionRequest]:
    """
    supervisor 쪽 목록 조회용
    - instructor-management.html 의 승인 대기 탭 등에서 사용
    """
    stmt = select(PartnerPromotionRequest).order_by(
        PartnerPromotionRequest.requested_at.desc()
    )
    if status:
        stmt = stmt.where(PartnerPromotionRequest.status == status)
    return db.execute(stmt).scalars().all()


def approve_promotion_request(
    db: Session,
    *,
    request_id: int,
    decided_reason: Optional[str] = None,
    target_role: Optional[str] = None,
) -> Tuple[PartnerPromotionRequest, Partner, PartnerUser]:
    """
    승격 요청 승인
    - 1) pending 상태의 PartnerPromotionRequest 조회
    - 2) _promote_user_to_partner_internal 로 partner / partner_user 생성 (멱등)
    - 3) 요청 레코드 status/decided_* 및 partner_id/partner_user_id 업데이트
    """
    req = db.get(PartnerPromotionRequest, request_id)
    if not req:
        raise PromotionNotFound(f"promotion request not found: id={request_id}")

    if req.status != "pending":
        # 이미 승인된 요청은 멱등 처리: 기존 partner/partner_user 있으면 그대로 반환
        if req.status == "approved" and req.partner_id and req.partner_user_id:
            partner = db.get(Partner, req.partner_id)
            puser = db.get(PartnerUser, req.partner_user_id)
            if partner and puser:
                return req, partner, puser
        raise PromotionConflict(f"promotion request already {req.status}")

    role = target_role or req.target_role or "partner_admin"

    # 실제 Partner / PartnerUser 생성 또는 재사용
    partner, puser = _promote_user_to_partner_internal(
        db,
        email=req.email,
        partner_name=req.requested_org_name,
        created_by=None,
        partner_user_role=role,
    )

    # 요청 레코드 업데이트
    req.status = "approved"
    req.decided_at = _utcnow()
    req.decided_reason = decided_reason
    req.partner_id = partner.id
    req.partner_user_id = puser.id
    req.target_role = role

    db.add(req)
    db.commit()
    db.refresh(req)

    return req, partner, puser


def reject_promotion_request(
    db: Session,
    *,
    request_id: int,
    decided_reason: Optional[str] = None,
) -> PartnerPromotionRequest:
    """
    승격 요청 거절
    - pending 상태만 거절 가능
    """
    req = db.get(PartnerPromotionRequest, request_id)
    if not req:
        raise PromotionNotFound(f"promotion request not found: id={request_id}")

    if req.status != "pending":
        raise PromotionConflict(f"promotion request already {req.status}")

    req.status = "rejected"
    req.decided_at = _utcnow()
    req.decided_reason = decided_reason

    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# ==============================
# Organizations
# ==============================
def create_org(
    db: Session,
    *,
    name: str,
    plan_id: Optional[int] = None,
    industry: Optional[str] = None,
    company_size: Optional[str] = None,
    status: str = "active",
    created_by: Optional[int] = None,
    notes: Optional[str] = None,
) -> Organization:
    # 0은 FK 불가 → None 처리
    if plan_id in (0, "0"):
        plan_id = None
    # 유효성 체크(선택)
    if plan_id is not None and db.get(Plan, plan_id) is None:
        raise ValueError(f"invalid plan_id={plan_id}")

    org = Organization(
        name=name,
        plan_id=plan_id,
        industry=industry,
        company_size=company_size,
        status=status,
        created_by=created_by,
        notes=notes,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def get_org(db: Session, org_id: int) -> Optional[Organization]:
    return db.get(Organization, org_id)


def list_orgs(
    db: Session,
    *,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> Sequence[Organization]:
    stmt = select(Organization).order_by(Organization.created_at.desc())
    if status:
        stmt = stmt.where(Organization.status == status)
    if q:
        stmt = stmt.where(Organization.name.ilike(f"%{q}%"))
    return db.execute(stmt).scalars().all()


def update_org(db: Session, org_id: int, **fields) -> Optional[Organization]:
    stmt = (
        update(Organization)
        .where(Organization.organization_id == org_id)
        .values(**fields)
        .returning(Organization)
    )
    row = db.execute(stmt).fetchone()
    if not row:
        return None
    db.commit()
    return row[0]


def delete_org(db: Session, org_id: int) -> bool:
    res = db.execute(delete(Organization).where(Organization.organization_id == org_id))
    db.commit()
    return res.rowcount > 0


# ==============================
# Convenience: bootstrap roles ?
# ==============================
def bootstrap_default_roles(db: Session) -> Sequence[UserRole]:
    defaults = [
        ("supervisor_admin", {"scope": "platform", "perm": ["all"]}),
        (
            "partner_admin",
            {
                "scope": "partner",
                "perm": ["manage_partner", "manage_courses", "manage_students"],
            },
        ),
        (
            "instructor",
            {"scope": "partner", "perm": ["manage_courses", "view_students"]},
        ),
        ("student", {"scope": "partner", "perm": ["practice"]}),
    ]
    out: list[UserRole] = []
    for name, perms in defaults:
        out.append(get_or_create_role(db, role_name=name, permissions=perms))
    return out


# ==============================
# Plans : 추후 기능
# ==============================
def create_plan(
    db: Session,
    *,
    name: str,
    billing_cycle: str = "monthly",
    price_mrr: float = 0,
    price_arr: float = 0,
    features_json: Optional[dict] = None,
    max_users: Optional[int] = None,
    is_active: bool = True,
) -> Plan:
    plan = Plan(
        plan_name=name,
        billing_cycle=billing_cycle,
        price_mrr=price_mrr,
        price_arr=price_arr,
        features_json=features_json,
        max_users=max_users,
        is_active=is_active,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_plan(db: Session, plan_id: int) -> Optional[Plan]:
    return db.get(Plan, plan_id)


def list_plans(db: Session, *, q: Optional[str] = None) -> Sequence[Plan]:
    stmt = select(Plan).order_by(Plan.plan_name)
    if q:
        stmt = stmt.where(Plan.plan_name.ilike(f"%{q}%"))
    return db.execute(stmt).scalars().all()


def update_plan(db: Session, plan_id: int, **fields) -> Optional[Plan]:
    stmt = (
        update(Plan)
        .where(Plan.plan_id == plan_id)
        .values(**fields)
        .returning(Plan)
    )
    row = db.execute(stmt).fetchone()
    if not row:
        return None
    db.commit()
    return row[0]


def delete_plan(db: Session, plan_id: int) -> bool:
    res = db.execute(delete(Plan).where(Plan.plan_id == plan_id))
    db.commit()
    return res.rowcount > 0
