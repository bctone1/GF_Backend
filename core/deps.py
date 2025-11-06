# core/deps.py
from __future__ import annotations
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
# fastapi 에서 stub 가짜 고정응답 제공
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models.user.account import User
from core.config import DB, DB_USER, DB_PASSWORD, DB_SERVER, DB_PORT, DB_NAME

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


def get_db() -> Session:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 인증 스텁 (추후 JWT로 교체)
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
