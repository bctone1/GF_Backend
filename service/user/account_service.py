# service/user/account_service.py
from __future__ import annotations

from typing import Dict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from crud.user import account as user_crud
from core.security import hash_password, verify_password, issue_tokens
from models.user.account import UserProfile
from schemas.user.account import (
    UserCreate,
    UserResponse,
    LoginInput,
    AuthTokens,
    UserProfileUpdate,
)


def signup(db: Session, payload: UserCreate) -> UserResponse:
    """
    기본 사용자 회원가입 서비스 레이어
    - 이메일 중복 체크
    - 비밀번호 해시
    - 프로필 분리(full_name)
    - user + profile + 기본 settings 생성
    """
    # 이메일 중복 체크
    if user_crud.get_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        )

    # 비밀번호 필수
    if not payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password required",
        )

    # 비밀번호 해시
    password_hash = hash_password(payload.password)

    # 프로필(full_name) 분리
    profile_in = {}
    if getattr(payload, "full_name", None):
        profile_in["full_name"] = payload.full_name

    # 클라이언트에서 status/default_role 임의 지정 못 하게 서버에서 고정
    user_in = {
        "email": payload.email,
        "password_hash": password_hash,
        "status": "active",
        "default_role": "member",
    }

    # user + profile + 기본 settings 생성
    user = user_crud.create_with_profile(
        db,
        user_in=user_in,
        profile_in=profile_in or None,
        ensure_settings=True,
    )

    return UserResponse.model_validate(user)


def login(
    db: Session,
    payload: LoginInput,
    meta: Dict[str, str],
) -> AuthTokens:
    """
    로그인 서비스 레이어
    - get_by_email + verify_password
    - 상태 체크(active/invited)
    - 기존 세션 종료
    - 새 로그인 세션 생성
    - 마지막 로그인 시간 업데이트
    - 토큰 발급
    """
    user = user_crud.get_by_email(db, email=payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    # 상태 체크
    if user.status not in ("active", "invited"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not active",
        )

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
    tokens = issue_tokens(user_id=user.user_id)
    return AuthTokens(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=getattr(tokens, "token_type", "bearer"),
    )


def update_my_profile(
    db: Session,
    me_id: int,
    payload: UserProfileUpdate,
) -> UserProfile:
    """
    내 프로필 업데이트 서비스 레이어
    - payload 에서 unset 은 제외하고 upsert_profile 호출
    """
    data = payload.model_dump(exclude_unset=True)
    return user_crud.upsert_profile(db, user_id=me_id, data=data)
