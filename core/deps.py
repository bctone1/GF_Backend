# core/deps.py
from __future__ import annotations
from typing import Optional, Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import DB, DB_USER, DB_PASSWORD, DB_SERVER, DB_PORT, DB_NAME

# user/partner 인증에 사용
from models.user.account import User
from models.partner.partner_core import PartnerUser  # 파트너 권한 확인용

# supervisor 인증·권한에 사용
from models.supervisor.core import (
    User as SupUser,
    UserRole,
    UserRoleAssignment,
)

_bearer = HTTPBearer(auto_error=False)


def _build_dsn() -> str:
    driver = "postgresql+psycopg2" if (DB or "").lower().startswith("postgres") else (DB or "postgresql+psycopg2")
    user = quote_plus(DB_USER) if DB_USER else ""
    pwd = quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
    auth = f"{user}:{pwd}@" if (user or pwd) else ""
    host = DB_SERVER or "localhost"
    port = DB_PORT or "5432"
    name = DB_NAME or "growfit"
    return f"{driver}://{auth}{host}:{port}/{name}"


ENGINE = create_engine(_build_dsn(), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autocommit=False, autoflush=False, future=True)


# ==============================
# DB 세션
# ==============================
def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==============================
# 인증 스텁 (JWT 교체 예정)
# Authorization: Bearer dev-access-{user_id}
# ==============================
def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Security(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = creds.credentials if creds else None
    prefix = "dev-access-"
    if not token or not token.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    uid_str = token[len(prefix):]
    if not uid_str.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    user = db.get(User, int(uid_str))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return user


def get_current_session_id(request: Request) -> Optional[int]:
    sid = request.headers.get("X-Session-Id")
    return int(sid) if sid and sid.isdigit() else None


# ==============================
# 파트너 권한 검사
# - 라우트 path의 {partner_id} 자동 주입
# - 관리자/매니저 전용 보호
# ==============================
ADMIN_ROLES = ("partner_admin", "partner_manager")


def get_current_partner_admin(
    partner_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartnerUser:
    # User PK 속성 호환 처리(user_id 또는 id)
    uid = getattr(current_user, "user_id", None) or getattr(current_user, "id", None)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    stmt = (
        select(PartnerUser)
        .where(
            PartnerUser.partner_id == partner_id,
            PartnerUser.user_id == uid,
            PartnerUser.is_active.is_(True),
        )
        .limit(1)
    )
    pu = db.execute(stmt).scalars().first()
    if not pu or pu.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return pu


# (선택) 파트너 소속 여부만 확인하고 싶을 때
def get_current_partner_member(
    partner_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartnerUser:
    uid = getattr(current_user, "user_id", None) or getattr(current_user, "id", None)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    stmt = (
        select(PartnerUser)
        .where(
            PartnerUser.partner_id == partner_id,
            PartnerUser.user_id == uid,
            PartnerUser.is_active.is_(True),
        )
        .limit(1)
    )
    pu = db.execute(stmt).scalars().first()
    if not pu:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return pu


# ==============================
# Supervisor 인증/권한
# - Authorization: Bearer sup-access-{supervisor_user_id}
# - 또는 개발 편의: X-Debug-Email: <supervisor-email>
# ==============================
def get_current_supervisor(
    request: Request,
    creds: HTTPAuthorizationCredentials = Security(_bearer),
    db: Session = Depends(get_db),
) -> SupUser:
    token = creds.credentials if creds else None
    prefix = "sup-access-"

    # 1) 토큰으로 식별
    if token and token.startswith(prefix):
        sid_str = token[len(prefix):]
        if not sid_str.isdigit():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
        sup = db.get(SupUser, int(sid_str))
        if not sup or (sup.status or "").lower() != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="inactive supervisor")
        return sup

    # 2) 개발용 이메일 헤더
    dbg_email = request.headers.get("X-Debug-Email")
    if dbg_email:
        stmt = select(SupUser).where(func.lower(SupUser.email) == func.lower(dbg_email))
        sup = db.execute(stmt).scalar_one_or_none()
        if not sup:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
        if (sup.status or "").lower() != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="inactive supervisor")
        return sup

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def require_supervisor_admin(
    me: SupUser = Depends(get_current_supervisor),
    db: Session = Depends(get_db),
) -> SupUser:
    """
    권한 체크:
    - 직접 컬럼: me.role == 'supervisor_admin'
    - 또는 역할 할당 테이블: user_role_assignments ↔ user_roles(role_name='supervisor_admin')
    """
    if (me.role or "").lower() == "supervisor_admin":
        return me

    stmt = (
        select(UserRoleAssignment)
        .join(UserRole, UserRole.role_id == UserRoleAssignment.role_id)
        .where(
            UserRoleAssignment.user_id == me.user_id,
            func.lower(UserRole.role_name) == "supervisor_admin",
        )
        .limit(1)
    )
    if db.execute(stmt).first():
        return me

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
