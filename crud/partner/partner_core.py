from __future__ import annotations
from typing import Optional, Sequence, Tuple
import random, string

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.partner.partner_core import Partner, PartnerUser
from models.user.account import AppUser


# ========= Exceptions =========
class PartnerError(Exception): ...
class PartnerNotFound(PartnerError): ...
class PartnerConflict(PartnerError): ...
class PartnerUserNotFound(PartnerError): ...
class PartnerUserConflict(PartnerError): ...


# ========= Helpers =========
def _gen_code(prefix: str = "PT", length: int = 6) -> str:
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{body}"

def _slugify(s: str, max_len: int = 16) -> str:
    base = "".join(ch for ch in s.upper() if ch.isalnum())
    return (base or "PARTNER")[:max_len]


# ========= Partner CRUD =========
def create_partner(
    db: Session,
    *,
    name: str,
    code: Optional[str] = None,
    status: str = "active",
    timezone: str = "UTC",
) -> Partner:
    base_code = (code or _slugify(name))[:16]
    try_code = base_code
    tries = 0
    while True:
        try:
            obj = Partner(name=name, code=try_code, status=status, timezone=timezone)
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
                try_code = _gen_code(prefix=_slugify(name)[:4] or "PT", length=6)

def get_partner(db: Session, partner_id: int) -> Optional[Partner]:
    return db.get(Partner, partner_id)

def get_partner_by_code(db: Session, code: str) -> Optional[Partner]:
    stmt = select(Partner).where(Partner.code == code).limit(1)
    return db.execute(stmt).scalar_one_or_none()

def list_partners(
    db: Session,
    *,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Partner]:
    stmt = select(Partner).order_by(Partner.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Partner.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Partner.name.ilike(like) | Partner.code.ilike(like))
    return db.execute(stmt).scalars().all()

def update_partner(db: Session, partner_id: int, **fields) -> Optional[Partner]:
    if "code" in fields:
        # 코드 변경은 유니크 충돌 가능
        fields["code"] = fields["code"][:16]
    stmt = (
        update(Partner)
        .where(Partner.id == partner_id)
        .values(**fields)
        .returning(Partner)
    )
    try:
        row = db.execute(stmt).fetchone()
        if not row:
            db.rollback()
            return None
        db.commit()
        return row[0]
    except IntegrityError:
        db.rollback()
        raise PartnerConflict("partner code already exists")

def delete_partner(db: Session, partner_id: int) -> bool:
    res = db.execute(delete(Partner).where(Partner.id == partner_id))
    db.commit()
    return res.rowcount > 0


# ========= PartnerUser CRUD =========
def _find_app_user_by_email(db: Session, email: str) -> Optional[AppUser]:
    stmt = select(AppUser).where(func.lower(AppUser.email) == func.lower(email)).limit(1)
    return db.execute(stmt).scalar_one_or_none()

def get_partner_user(db: Session, partner_user_id: int) -> Optional[PartnerUser]:
    return db.get(PartnerUser, partner_user_id)

def get_partner_user_by_email(db: Session, *, partner_id: int, email: str) -> Optional[PartnerUser]:
    stmt = (
        select(PartnerUser)
        .where(
            PartnerUser.partner_id == partner_id,
            func.lower(PartnerUser.email) == func.lower(email),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()

def list_partner_users(
    db: Session,
    *,
    partner_id: int,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[PartnerUser]:
    stmt = (
        select(PartnerUser)
        .where(PartnerUser.partner_id == partner_id)
        .order_by(PartnerUser.created_at.desc())
        .limit(limit).offset(offset)
    )
    if role:
        stmt = stmt.where(PartnerUser.role == role)
    if is_active is not None:
        stmt = stmt.where(PartnerUser.is_active.is_(is_active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            PartnerUser.full_name.ilike(like) |
            PartnerUser.email.ilike(like) |
            (PartnerUser.phone.isnot(None) & PartnerUser.phone.ilike(like))
        )
    return db.execute(stmt).scalars().all()

def add_partner_user(
    db: Session,
    *,
    partner_id: int,
    email: str,
    full_name: Optional[str] = None,
    role: str = "partner",  # 기본값 partner_admin → partner 로 변경
    phone: Optional[str] = None,
    is_active: bool = True,
    user_id: Optional[int] = None,  # user.users PK. 주어지지 않으면 email로 조회
) -> PartnerUser:
    # 멱등: 이미 매핑되어 있으면 반환
    existing = get_partner_user_by_email(db, partner_id=partner_id, email=email)
    if existing:
        return existing

    app_user_id = user_id
    if app_user_id is None:
        app_user = _find_app_user_by_email(db, email)
        app_user_id = getattr(app_user, "user_id", None) if app_user else None

    obj = PartnerUser(
        partner_id=partner_id,
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
        # email 유니크/ partner_id+user_id 유니크 위반 분기
        raise PartnerUserConflict("duplicate mapping or email in this partner") from e
    db.refresh(obj)
    return obj

def update_partner_user(db: Session, partner_user_id: int, **fields) -> Optional[PartnerUser]:
    # 이메일 변경은 citext + 유니크 고려
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
def ensure_partner_and_admin(
    db: Session,
    *,
    partner_name: str,
    partner_code: Optional[str],
    admin_email: str,
    admin_full_name: Optional[str] = None,
) -> Tuple[Partner, PartnerUser]:
    """
    파트너 없으면 생성, 있으면 사용. 관리자(대표 강사) 없으면 생성.
    """
    partner = None
    if partner_code:
        partner = get_partner_by_code(db, partner_code)
    if not partner:
        # 이름 기반 검색은 충돌이 있을 수 있어 code 우선
        try:
            partner = create_partner(db, name=partner_name, code=partner_code or _slugify(partner_name))
        except PartnerConflict:
            partner = get_partner_by_code(db, partner_code or _slugify(partner_name))

    puser = get_partner_user_by_email(db, partner_id=partner.id, email=admin_email)
    if not puser:
        puser = add_partner_user(
            db,
            partner_id=partner.id,
            email=admin_email,
            full_name=admin_full_name or admin_email,
            role="partner",  # partner_admin → partner
            is_active=True,
        )
    return partner, puser
