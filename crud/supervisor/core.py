# crud/supervisor/core.py
from __future__ import annotations
from typing import Optional, Sequence, Tuple
from datetime import datetime, timezone
import random, string

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.supervisor.core import (
    Plan, Organization, SupervisorUser as SupUser, UserRole, UserRoleAssignment, Session as SupSession,
)
# user tier 가입 사용자
from models.user.account import AppUser as AppUser  # table: user.users (PK: user_id, email)
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
def create_supervisor_user(db: Session, *, org_id: int, email: str, name: str,
                           role: str = "supervisor_admin", status: str = "active") -> SupUser:
    sup = SupUser(
        organization_id=org_id, email=email, name=name, role=role, status=status,
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
def get_or_create_role(db: Session, *, role_name: str, permissions: Optional[dict] = None) -> UserRole:
    stmt = select(UserRole).where(UserRole.role_name == role_name)
    role = db.execute(stmt).scalar_one_or_none()
    if role:
        return role
    role = UserRole(role_name=role_name, permissions_json=permissions or {})
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

def assign_role(db: Session, *, user_id: int, role_name: str, assigned_by: Optional[int] = None) -> UserRoleAssignment:
    role = get_or_create_role(db, role_name=role_name)
    # 멱등: 이미 있으면 리턴
    stmt = select(UserRoleAssignment).where(
        UserRoleAssignment.user_id == user_id,
        UserRoleAssignment.role_id == role.role_id,
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        return existing
    ura = UserRoleAssignment(user_id=user_id, role_id=role.role_id, assigned_by=assigned_by)
    db.add(ura)
    db.commit()
    db.refresh(ura)
    return ura


# ==============================
# Promotion: user.users -> Partner
# ==============================
class PromotionError(Exception): ...
class PromotionNotFound(PromotionError): ...
class PromotionConflict(PromotionError): ...

def promote_user_to_partner(
    db: Session,
    *,
    email: str,
    partner_name: str,
    partner_code: Optional[str] = None,
    created_by: Optional[int] = None,
    partner_user_role: str = "partner_admin",
) -> Tuple[Partner, PartnerUser]:
    """
    1) user.users에서 가입 사용자 존재 확인
    2) partners/partner_users 멱등 승격
    """
    # 1) 가입 사용자 확인 (user.users)
    app_user = db.execute(
        select(AppUser).where(func.lower(AppUser.email) == func.lower(email))
    ).scalar_one_or_none()
    if not app_user:
        raise PromotionNotFound(f"no user.users found for email={email}")

    # 2) 파트너 코드/이름 정리
    code = (partner_code or _slugify_code(partner_name))[:16]

    # 3) 멱등: 동일 code 파트너가 있으면 재사용
    partner = db.execute(select(Partner).where(Partner.code == code)).scalar_one_or_none()
    if not partner:
        # code 충돌 피벗 처리
        try_code = code
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
                    try_code = _gen_code(prefix=_slugify_code(partner_name)[:4], length=6)
                else:
                    try_code = f"{code}{tries}"

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
            full_name=getattr(app_user, "full_name", None) or getattr(app_user, "name", None) or email,
            email=app_user.email,
            role=partner_user_role,
            is_active=True,
        )
        db.add(pu)

    # 5) 커밋
    db.commit()
    db.refresh(partner)
    db.refresh(pu)
    return partner, pu



# ==============================
# Organizations
# ==============================
def create_org(db: Session, *, name: str, plan_id: Optional[int] = None,
               industry: Optional[str] = None, company_size: Optional[str] = None,
               status: str = "active", created_by: Optional[int] = None,
               notes: Optional[str] = None) -> Organization:

    # 0은 FK 불가 → None 처리
    if plan_id in (0, "0"):
        plan_id = None
    # 유효성 체크(선택)
    if plan_id is not None and db.get(Plan, plan_id) is None:
        raise ValueError(f"invalid plan_id={plan_id}")

    org = Organization(
        name=name, plan_id=plan_id, industry=industry, company_size=company_size,
        status=status, created_by=created_by, notes=notes,
    )
    db.add(org); db.commit(); db.refresh(org)
    return org

def get_org(db: Session, org_id: int) -> Optional[Organization]:
    return db.get(Organization, org_id)

def list_orgs(db: Session, *, status: Optional[str] = None, q: Optional[str] = None) -> Sequence[Organization]:
    stmt = select(Organization).order_by(Organization.created_at.desc())
    if status:
        stmt = stmt.where(Organization.status == status)
    if q:
        stmt = stmt.where(Organization.name.ilike(f"%{q}%"))
    return db.execute(stmt).scalars().all()

def update_org(db: Session, org_id: int, **fields) -> Optional[Organization]:
    stmt = update(Organization).where(Organization.organization_id == org_id).values(**fields).returning(Organization)
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
        ("partner_admin", {"scope": "partner", "perm": ["manage_partner", "manage_courses", "manage_students"]}),
        ("instructor", {"scope": "partner", "perm": ["manage_courses", "view_students"]}),
        ("student", {"scope": "partner", "perm": ["practice"]}),
    ]
    out = []
    for name, perms in defaults:
        out.append(get_or_create_role(db, role_name=name, permissions=perms))
    return out




# ==============================
# Plans
# ==============================
def create_plan(db: Session, *, name: str, billing_cycle: str = "monthly",
                price_mrr: float = 0, price_arr: float = 0,
                features_json: Optional[dict] = None, max_users: Optional[int] = None,
                is_active: bool = True) -> Plan:
    plan = Plan(
        plan_name=name, billing_cycle=billing_cycle, price_mrr=price_mrr, price_arr=price_arr,
        features_json=features_json, max_users=max_users, is_active=is_active,
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
    stmt = update(Plan).where(Plan.plan_id == plan_id).values(**fields).returning(Plan)
    row = db.execute(stmt).fetchone()
    if not row:
        return None
    db.commit()
    return row[0]

def delete_plan(db: Session, plan_id: int) -> bool:
    res = db.execute(delete(Plan).where(Plan.plan_id == plan_id))
    db.commit()
    return res.rowcount > 0
