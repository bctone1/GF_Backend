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
from models.user.account import AppUser
from models.partner.partner_core import PartnerUser  # 파트너 권한 확인

# supervisor 인증·권한에 사용
from models.supervisor.core import (
    SupervisorUser as SupUser,
    Organization,
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
) -> AppUser:
    token = creds.credentials if creds else None
    prefix = "dev-access-"
    if not token or not token.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    uid_str = token[len(prefix):]
    if not uid_str.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    user = db.get(AppUser, int(uid_str))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return user


def get_current_session_id(request: Request) -> Optional[int]:
    sid = request.headers.get("X-Session-Id")
    return int(sid) if sid and sid.isdigit() else None


# ==============================
# 파트너 권한 검사
# ==============================
ADMIN_ROLES = ("partner_admin", "partner_manager")


def get_current_partner_admin(
    partner_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),  # ✅ 타입
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
    if not pu or pu.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return pu


def get_current_partner_member(
    partner_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
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
# - 개발 모드 브리지:  Bearer dev-access-{user_id} → 같은 이메일 SupervisorUser 매칭/자동생성
# - 개발 편의 헤더:    X-Debug-Email: <supervisor-email>
# ==============================
def get_current_supervisor(
    request: Request,
    creds: HTTPAuthorizationCredentials = Security(_bearer),
    db: Session = Depends(get_db),
) -> SupUser:
    token = creds.credentials if creds else None

    # 1) sup-access-* 직접 인증
    sup_prefix = "sup-access-"
    if token and token.startswith(sup_prefix):
        sid_str = token[len(sup_prefix):]
        if not sid_str.isdigit():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
        sup = db.get(SupUser, int(sid_str))
        if not sup or (sup.status or "").lower() != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="inactive supervisor")
        return sup

    # 2) dev-access-* 브리지 (AppUser → SupervisorUser)
    dev_prefix = "dev-access-"
    if token and token.startswith(dev_prefix):
        uid_str = token[len(dev_prefix):]
        if not uid_str.isdigit():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

        app_user = db.get(AppUser, int(uid_str))
        if not app_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

        # 같은 이메일의 SupervisorUser 검색
        sup = db.execute(
            select(SupUser).where(func.lower(SupUser.email) == func.lower(app_user.email))
        ).scalar_one_or_none()
        if sup and (sup.status or "").lower() == "active":
            return sup

        # 없으면 조직 하나 확보 후 자동 생성
        org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
        if not org:
            org = Organization(name="GrowFit Platform", status="active")
            db.add(org)
            db.flush()

        sup = SupUser(
            organization_id=org.organization_id,
            email=app_user.email,
            name=getattr(app_user, "full_name", None)
            or getattr(app_user, "name", None)
            or app_user.email,
            role="supervisor_admin",
            status="active",
        )
        db.add(sup)
        db.commit()
        db.refresh(sup)
        return sup

    # 3) 개발용 이메일 헤더
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
    sup: SupUser = Depends(get_current_supervisor),
) -> SupUser:
    """
    supervisor_admin 권한 필수
    - get_current_supervisor 로 SupUser를 가져온 뒤 role 검사
    - 엔드포인트에서 `_ = Depends(require_supervisor_admin)` 이나
      `me = Depends(require_supervisor_admin)` 둘 다 가능
    """
    role = (sup.role or "").lower()
    if role != "supervisor_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return sup
