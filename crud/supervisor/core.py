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
from models.partner.partner_core import Org, PartnerUser


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


def _promote_user_to_partner_internal(
    db: Session,
    *,
    email: str,
    partner_name: str,              # 실제로는 Org 이름
    created_by: Optional[int] = None,
    partner_user_role: str = "partner",
) -> Tuple[Org, PartnerUser]:
    """
    실제 partner.org / partner.partner(PartnerUser)를 만드는 하위 유틸.

    - 주어진 email 에 해당하는 AppUser 를 찾고
    - partner_name 기반 Org 를 생성/재사용
    - 그 Org 와 AppUser 를 연결하는 PartnerUser 를 생성/재사용
    - 트랜잭션/상태 전이는 서비스 레이어에서 처리
    """
    # 1) 가입 사용자 확인 (user.users)
    app_user = db.execute(
        select(AppUser).where(func.lower(AppUser.email) == func.lower(email))
    ).scalar_one_or_none()
    if not app_user:
        raise PromotionNotFound(f"no user.users found for email={email}")

    # 2) Org 코드/이름 정리 (코드는 내부에서 자동 생성)
    base_code = _slugify_code(partner_name)[:16]

    # 3) 멱등: 동일 code Org 가 있으면 재사용
    org = db.execute(
        select(Org).where(Org.code == base_code)
    ).scalar_one_or_none()

    if not org:
        try_code = base_code
        tries = 0
        while True:
            try:
                org = Org(
                    name=partner_name,
                    code=try_code,
                    status="active",
                    created_by=created_by,
                    # timezone 은 기본값 'UTC' 사용
                )
                db.add(org)
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

    # 4) 멱등: 이미 PartnerUser 매핑이 있으면 그대로 반환
    pu = db.execute(
        select(PartnerUser).where(
            PartnerUser.partner_id == org.id,          # partner_id = org_id 역할
            PartnerUser.user_id == app_user.user_id,
        )
    ).scalar_one_or_none()

    if not pu:
        pu = PartnerUser(
            partner_id=org.id,
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
    db.refresh(org)
    db.refresh(pu)
    return org, pu

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
