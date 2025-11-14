# service/user/account_service.py
from __future__ import annotations

from typing import Dict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from crud.user import account as user_crud
from service.auth import hash_password, verify_password, issue_tokens
from schemas.user.account import (
    UserCreate,
    UserResponse,
    LoginInput,
    AuthTokens,
)


def signup(db: Session, payload: UserCreate) -> UserResponse:
    data = payload.model_dump()
    raw_pw = data.pop("password", None)
    if not raw_pw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password required",
        )

    # 비밀번호 해시
    data["password_hash"] = hash_password(raw_pw)

    # 프로필(full_name) 분리
    full_name = data.pop("full_name", None)
    profile_in = {"full_name": full_name} if full_name else None

    # 이메일 중복 체크 (옵션이지만 명시적으로 처리)
    if user_crud.get_by_email(db, data["email"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        )

    # user + profile + 기본 settings 생성
    user = user_crud.create_with_profile(
        db,
        user_in=data,
        profile_in=profile_in,
        ensure_settings=True,
    )

    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        default_role=user.default_role,
    )


def login(
    db: Session,
    payload: LoginInput,
    meta: Dict[str, str],
) -> AuthTokens:
    user = user_crud.get_by_email(db, email=payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    # single_current=True 와 같은 효과:
    # 1) 기존 current 세션 모두 종료
    user_crud.close_all_sessions_for_user(db, user_id=user.user_id)

    # 2) 새 로그인 세션 생성
    user_crud.create_login_session(
        db,
        user_id=user.user_id,
        data={
            "device_name": meta.get("device_name"),
            "ip_address": meta.get("ip_address"),
            "location": meta.get("location"),
            "user_agent": meta.get("user_agent"),
        },
    )

    # 3) 마지막 로그인 시간 업데이트
    user_crud.set_last_login(db, user_id=user.user_id)

    # 4) 토큰 발급
    return issue_tokens(user_id=user.user_id)
