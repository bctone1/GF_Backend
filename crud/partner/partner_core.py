from __future__ import annotations
from typing import Optional, Sequence, Tuple
import random
import string

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.partner.partner_core import Org, Partner
from models.user.account import AppUser


# ========= Exceptions =========
class OrgError(Exception):
    ...


class OrgNotFound(OrgError):
    ...


class OrgConflict(OrgError):
    ...


class PartnerError(OrgError):
    ...


class PartnerNotFound(PartnerError):
    ...


class PartnerConflict(PartnerError):
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


# ========= Partner CRUD =========
def _find_app_user_by_email(db: Session, email: str) -> Optional[AppUser]:
    stmt = select(AppUser).where(func.lower(AppUser.email) == func.lower(email)).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def get_partner(db: Session, partner_id: int) -> Optional[Partner]:
    return db.get(Partner, partner_id)


def get_partner_by_email(
    db: Session,
    *,
    org_id: int,
    email: str,
) -> Optional[Partner]:
    """
    특정 Org 내에서 이메일로 파트너(강사/어시) 조회.
    """
    stmt = (
        select(Partner)
        .where(
            Partner.org_id == org_id,
            func.lower(Partner.email) == func.lower(email),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_partners(
    db: Session,
    *,
    org_id: int,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Partner]:
    """
    특정 Org에 속한 파트너(강사/어시) 리스트.
    org_id → Partner.org_id.
    """
    stmt = (
        select(Partner)
        .where(Partner.org_id == org_id)
        .order_by(Partner.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if role:
        stmt = stmt.where(Partner.role == role)
    if is_active is not None:
        stmt = stmt.where(Partner.is_active.is_(is_active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Partner.full_name.ilike(like)
            | Partner.email.ilike(like)
            | (Partner.phone.isnot(None) & Partner.phone.ilike(like))
        )
    return db.execute(stmt).scalars().all()


def add_partner(
    db: Session,
    *,
    org_id: int,
    email: str,
    full_name: Optional[str] = None,
    role: str = "partner",  # partner | assistant
    phone: Optional[str] = None,
    is_active: bool = True,
    user_id: Optional[int] = None,  # user.users PK. 주어지지 않으면 email로 조회
) -> Partner:
    """
    Org에 속한 Partner(강사/어시) 추가.
    - 이미 org_id + email 매핑이 있으면 그대로 반환 (멱등)
    - AppUser가 존재하면 user_id와 users.partner_id 를 함께 세팅
    """
    existing = get_partner_by_email(db, org_id=org_id, email=email)
    if existing:
        return existing

    app_user_id = user_id
    if app_user_id is None:
        app_user = _find_app_user_by_email(db, email)
        app_user_id = getattr(app_user, "user_id", None) if app_user else None

    partner = Partner(
        org_id=org_id,
        user_id=app_user_id,
        full_name=full_name or email,
        email=email,
        phone=phone,
        role=role,
        is_active=is_active,
    )
    db.add(partner)
    try:
        # 먼저 Partner 레코드 INSERT
        db.flush()

        # AppUser가 있으면 users.partner_id도 같이 연결
        if app_user_id is not None:
            user = db.get(AppUser, app_user_id)
            if user:
                user.partner_id = partner.id
                db.add(user)

        db.commit()
    except IntegrityError as e:
        db.rollback()
        # email 유니크 / user_id 유니크 위반 등
        raise PartnerConflict("duplicate mapping or email/user in this org") from e

    db.refresh(partner)
    return partner


def update_partner(db: Session, partner_id: int, **fields) -> Optional[Partner]:
    """
    Partner 정보 수정.
    user_id가 변경되는 경우 users.partner_id 일관성도 함께 맞춰줌.
    """
    partner = db.get(Partner, partner_id)
    if not partner:
        return None

    # user_id는 특별 취급
    new_user_id = fields.pop("user_id", None) if "user_id" in fields else None
    old_user_id = partner.user_id

    # 일반 필드 업데이트
    for key, value in fields.items():
        setattr(partner, key, value)

    # user_id 변경 처리
    if new_user_id is not None and new_user_id != old_user_id:
        # 예전 유저의 partner_id 정리
        if old_user_id is not None:
            old_user = db.get(AppUser, old_user_id)
            if old_user and old_user.partner_id == partner_id:
                old_user.partner_id = None
                db.add(old_user)

        # 새 유저에 partner_id 세팅
        if new_user_id is not None:
            new_user = db.get(AppUser, new_user_id)
            if new_user:
                new_user.partner_id = partner_id
                db.add(new_user)

        partner.user_id = new_user_id

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise PartnerConflict("email or mapping conflict") from e

    db.refresh(partner)
    return partner


def deactivate_partner(db: Session, partner_id: int) -> Optional[Partner]:
    return update_partner(db, partner_id, is_active=False)


def change_partner_role(db: Session, partner_id: int, role: str) -> Optional[Partner]:
    return update_partner(db, partner_id, role=role)


def remove_partner(db: Session, partner_id: int) -> bool:
    """
    Partner 삭제 시, 연결된 AppUser.partner_id 도 정리.
    """
    partner = db.get(Partner, partner_id)
    if not partner:
        return False

    if partner.user_id is not None:
        user = db.get(AppUser, partner.user_id)
        if user and user.partner_id == partner_id:
            user.partner_id = None
            db.add(user)

    db.delete(partner)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False

    return True


# ========= Convenience =========
def ensure_org_and_admin(
    db: Session,
    *,
    org_name: str,
    org_code: Optional[str],
    admin_email: str,
    admin_full_name: Optional[str] = None,
) -> Tuple[Org, Partner]:
    """
    Org(기관) 없으면 생성, 있으면 재사용.
    해당 Org의 관리자(대표 강사 역할) 없으면 Partner 생성.
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

    partner = get_partner_by_email(db, org_id=org.id, email=admin_email)
    if not partner:
        partner = add_partner(
            db,
            org_id=org.id,
            email=admin_email,
            full_name=admin_full_name or admin_email,
            role="partner",
            is_active=True,
        )

    return org, partner
