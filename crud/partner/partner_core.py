from __future__ import annotations
from typing import Optional, Sequence, Tuple
import random
import string

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.partner.partner_core import Org, PartnerUser   # Org, PartnerUser로 변경
from models.user.account import AppUser


# ========= Exceptions =========
class OrgError(Exception):
    ...


class OrgNotFound(OrgError):
    ...


class OrgConflict(OrgError):
    ...


class PartnerUserError(OrgError):
    ...


class PartnerUserNotFound(PartnerUserError):
    ...


class PartnerUserConflict(PartnerUserError):
    ...


# ========= Helpers =========
def _gen_code(prefix: str = "ORG", length: int = 6) -> str:
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{body}"


def _slugify(s: str, max_len: int = 16) -> str:
    base = "".join(ch for ch in s.upper() if ch.isalnum())
    return (base or "ORG")[:max_len]


# ========= Org CRUD =========
def create_org(
    db: Session,
    *,
    name: str,
    code: Optional[str] = None,
    status: str = "active",
    timezone: str = "UTC",
) -> Org:
    """
    Org(기관) 생성.
    code가 없으면 name 기반으로 slug 생성, 유니크 충돌 시 자동 재시도.
    """
    base_code = (code or _slugify(name))[:16]
    try_code = base_code
    tries = 0

    while True:
        try:
            obj = Org(name=name, code=try_code, status=status, timezone=timezone)
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj
        except IntegrityError:
            db.rollback()
            tries += 1
            if tries <= 3:
                try_code = f"{base_code}{tries}"
            else:
                try_code = _gen_code(prefix=_slugify(name)[:4] or "ORG", length=6)


def get_org(db: Session, org_id: int) -> Optional[Org]:
    return db.get(Org, org_id)


def get_org_by_code(db: Session, code: str) -> Optional[Org]:
    stmt = select(Org).where(Org.code == code).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def list_orgs(
    db: Session,
    *,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Org]:
    stmt = (
        select(Org)
        .order_by(Org.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(Org.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Org.name.ilike(like) | Org.code.ilike(like))
    return db.execute(stmt).scalars().all()


def update_org(db: Session, org_id: int, **fields) -> Optional[Org]:
    if "code" in fields and fields["code"] is not None:
        fields["code"] = fields["code"][:16]

    stmt = (
        update(Org)
        .where(Org.id == org_id)
        .values(**fields)
        .returning(Org)
    )
    try:
        row = db.execute(stmt).fetchone()
        if not row:
            db.rollback()
            return None
        db.commit()
        return row[0]
    except IntegrityError as e:
        db.rollback()
        raise OrgConflict("org code already exists") from e


def delete_org(db: Session, org_id: int) -> bool:
    res = db.execute(delete(Org).where(Org.id == org_id))
    db.commit()
    return res.rowcount > 0


# ========= PartnerUser CRUD =========
def _find_app_user_by_email(db: Session, email: str) -> Optional[AppUser]:
    stmt = select(AppUser).where(func.lower(AppUser.email) == func.lower(email)).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def get_partner_user(db: Session, partner_user_id: int) -> Optional[PartnerUser]:
    return db.get(PartnerUser, partner_user_id)


def get_partner_user_by_email(
    db: Session,
    *,
    org_id: int,
    email: str,
) -> Optional[PartnerUser]:
    """
    org_id = PartnerUser.partner_id (FK → partner.org.id)
    """
    stmt = (
        select(PartnerUser)
        .where(
            PartnerUser.partner_id == org_id,
            func.lower(PartnerUser.email) == func.lower(email),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_partner_users(
    db: Session,
    *,
    org_id: int,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[PartnerUser]:
    """
    특정 Org에 속한 강사/어시 리스트.
    org_id → PartnerUser.partner_id 로 매핑.
    """
    stmt = (
        select(PartnerUser)
        .where(PartnerUser.partner_id == org_id)
        .order_by(PartnerUser.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if role:
        stmt = stmt.where(PartnerUser.role == role)
    if is_active is not None:
        stmt = stmt.where(PartnerUser.is_active.is_(is_active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            PartnerUser.full_name.ilike(like)
            | PartnerUser.email.ilike(like)
            | (PartnerUser.phone.isnot(None) & PartnerUser.phone.ilike(like))
        )
    return db.execute(stmt).scalars().all()


def add_partner_user(
    db: Session,
    *,
    org_id: int,
    email: str,
    full_name: Optional[str] = None,
    role: str = "partner",  # partner | assistant
    phone: Optional[str] = None,
    is_active: bool = True,
    user_id: Optional[int] = None,  # user.users PK. 주어지지 않으면 email로 조회
) -> PartnerUser:
    """
    Org에 속한 PartnerUser(강사/어시) 추가.
    - 이미 org_id + email 매핑이 있으면 그대로 반환 (멱등)
    """
    existing = get_partner_user_by_email(db, org_id=org_id, email=email)
    if existing:
        return existing

    app_user_id = user_id
    if app_user_id is None:
        app_user = _find_app_user_by_email(db, email)
        app_user_id = getattr(app_user, "user_id", None) if app_user else None

    obj = PartnerUser(
        partner_id=org_id,            # FK → partner.org.id
        user_id=app_user_id,
        full_name=full_name or email,
        email=email,
        phone=phone,
        role=role,
        is_active=is_active,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # email 유니크 / (partner_id, user_id) 유니크 위반
        raise PartnerUserConflict("duplicate mapping or email in this org") from e
    db.refresh(obj)
    return obj


def update_partner_user(db: Session, partner_user_id: int, **fields) -> Optional[PartnerUser]:
    stmt = (
        update(PartnerUser)
        .where(PartnerUser.id == partner_user_id)
        .values(**fields)
        .returning(PartnerUser)
    )
    try:
        row = db.execute(stmt).fetchone()
        if not row:
            db.rollback()
            return None
        db.commit()
        return row[0]
    except IntegrityError as e:
        db.rollback()
        raise PartnerUserConflict("email or mapping conflict") from e


def deactivate_partner_user(db: Session, partner_user_id: int) -> Optional[PartnerUser]:
    return update_partner_user(db, partner_user_id, is_active=False)


def change_partner_user_role(db: Session, partner_user_id: int, role: str) -> Optional[PartnerUser]:
    return update_partner_user(db, partner_user_id, role=role)


def remove_partner_user(db: Session, partner_user_id: int) -> bool:
    res = db.execute(delete(PartnerUser).where(PartnerUser.id == partner_user_id))
    db.commit()
    return res.rowcount > 0


# ========= Convenience =========
def ensure_org_and_admin(
    db: Session,
    *,
    org_name: str,
    org_code: Optional[str],
    admin_email: str,
    admin_full_name: Optional[str] = None,
) -> Tuple[Org, PartnerUser]:
    """
    Org(기관) 없으면 생성, 있으면 재사용.
    해당 Org의 관리자(대표 강사 역할) 없으면 PartnerUser 생성.
    """
    org: Optional[Org] = None

    if org_code:
        org = get_org_by_code(db, org_code)

    if not org:
        try:
            org = create_org(
                db,
                name=org_name,
                code=org_code or _slugify(org_name),
            )
        except OrgConflict:
            org = get_org_by_code(db, org_code or _slugify(org_name))

    puser = get_partner_user_by_email(db, org_id=org.id, email=admin_email)
    if not puser:
        puser = add_partner_user(
            db,
            org_id=org.id,
            email=admin_email,
            full_name=admin_full_name or admin_email,
            role="partner",
            is_active=True,
        )

    return org, puser
