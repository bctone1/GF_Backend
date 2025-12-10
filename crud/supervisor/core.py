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
from models.user.account import AppUser, UserProfile
from models.partner.partner_core import Org, Partner as PartnerUser

# ==============================
# helpers
# ==============================
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _gen_code(prefix: str = "ORG", length: int = 6) -> str:
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{body}"


def _slugify_code(name: str, max_len: int = 12) -> str:
    base = "".join(ch for ch in name.upper() if ch.isalnum())
    base = base[: max_len] or "ORG"
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
# Promotion: PartnerPromotionRequest 관련 헬퍼
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

# 내부 유틸: AppUser(email)을 Org + PartnerUser 로 승격
def _promote_user_to_partner_internal(
    db: Session,
    *,
    email: str,
    partner_name: str,
    created_by: int | None,
    partner_user_role: str | None = None,
) -> tuple[Org, PartnerUser]:
    """
    - email 로 AppUser 찾기
    - partner_name 으로 Org 찾거나 생성
    - Org 안에서 (org_id, user_id) 기준으로 PartnerUser 찾거나 생성
    """

    # 0) AppUser 조회
    user = (
        db.query(AppUser)
        .filter(AppUser.email == email)
        .first()
    )
    if not user:
        # 원래 쓰던 예외 있으면 그대로 사용
        raise PromotionNotFound("user_not_found")

    # 1) Org 찾기 or 생성 (기관)
    org = (
        db.query(Org)
        .filter(Org.name == partner_name)
        .order_by(Org.id)
        .first()
    )
    if not org:
        org = Org(
            name=partner_name,
            code=f"ORG-{user.user_id}",  # 간단한 코드(임시용) – 나중에 규칙 바꿔도 됨
            timezone="UTC",
            status="active",
            created_by=created_by,
        )
        db.add(org)
        db.flush()  # org.id 확보

    # 2) Org 안에서 PartnerUser 찾기 or 생성 (강사/어시스턴트)
    partner_user = (
        db.query(PartnerUser)
        .filter(
            PartnerUser.org_id == org.id,          # 여기서 org_id 사용
            PartnerUser.user_id == user.user_id,
        )
        .order_by(PartnerUser.id)
        .first()
    )

    if not partner_user:
        full_name = (
            getattr(user, "full_name", None)
            or getattr(user, "name", None)
            or user.email
        )
        partner_user = PartnerUser(
            org_id=org.id,
            user_id=user.user_id,
            full_name=full_name,
            email=user.email,
            role=partner_user_role or "partner",
            is_active=True,
        )
        db.add(partner_user)
        db.flush()

    return org, partner_user




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
# Convenience: bootstrap roles
# ==============================
def bootstrap_default_roles(db: Session) -> Sequence[UserRole]:
    defaults = [
        ("supervisor_admin", {"scope": "platform", "perm": ["all"]}),
        (
            "partner",
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
