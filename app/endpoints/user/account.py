# app/endpoints/user/account.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from core.security import hash_password, verify_password, issue_tokens

from crud.user import account as user_crud
from models.user.account import AppUser
from schemas.user.account import (
    LoginInput,
    AuthTokens,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserProfileUpdate,
    UserProfileResponse,
    UserSecuritySettingUpdate,
    UserSecuritySettingResponse,
    UserPrivacySettingUpdate,
    UserPrivacySettingResponse,
    UserLoginSessionResponse,
)

router = APIRouter()


# ==============================
# Auth: signup / login
# ==============================

@router.post("/user/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def user_signup(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    """
    기본 사용자 회원가입.
    - email 중복 체크
    - password 해시 후 저장
    - 프로필/설정 생성
    """
    if user_crud.get_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already exists")

    password_hash = hash_password(payload.password)

    user_in = {
        "email": payload.email,
        "password_hash": password_hash,
        "status": payload.status or "active",
        "default_role": payload.default_role or "member",
    }

    profile_in = {}
    if payload.full_name:
        profile_in["full_name"] = payload.full_name

    app_user = user_crud.create_with_profile(
        db,
        user_in=user_in,
        profile_in=profile_in or None,
        ensure_settings=True,
    )
    return UserResponse.model_validate(app_user)


@router.post("/user/login", response_model=AuthTokens)
def user_login(
    payload: LoginInput,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    이메일/비밀번호 기반 로그인.
    - 비밀번호 검증
    - last_login_at 업데이트
    - 로그인 세션 기록
    - 토큰 발급
    """
    app_user = user_crud.get_by_email(db, payload.email)
    if not app_user or not verify_password(payload.password, app_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    # 상태 체크 (필요 시)
    if app_user.status not in ("active", "invited"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user is not active")

    # 마지막 로그인 갱신
    user_crud.set_last_login(db, user_id=app_user.user_id)

    # 로그인 세션 기록
    client = request.client
    ip = client.host if client else None
    ua = request.headers.get("user-agent")
    session_data = {
        "device_name": None,
        "ip_address": ip,
        "location": None,
        "user_agent": ua,
    }
    user_crud.create_login_session(db, user_id=app_user.user_id, data=session_data)

    # 토큰 발급 (dev-access-<user_id> 등)
    # 투두: issue_tokens 구현/경로에 맞게 조정
    tokens = issue_tokens(app_user.user_id)
    # issue_tokens 가 AuthTokens 형태를 그대로 돌려주지 않는다면 매핑 필요
    return AuthTokens(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type if hasattr(tokens, "token_type") else "bearer",
    )


# ==============================
# Me: 기본 계정 정보
# ==============================

@router.get("/my", response_model=UserResponse)
def get_my_account(
    me: AppUser = Depends(get_current_user),
) -> UserResponse:
    """
    현재 로그인한 사용자 기본 정보.
    """
    return UserResponse.model_validate(me)


@router.patch("/my", response_model=UserResponse)
def update_my_account(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> UserResponse:
    """
    내 계정 정보 수정.
    - email 변경
    - password 변경 시 해시 재계산
    - status/default_role 은 자기 계정에서 수정하지 않도록 무시
    """
    data = payload.model_dump(exclude_unset=True)

    # 비밀번호는 hash 로 변환해서 저장
    if "password" in data:
        new_password = data.pop("password")
        data["password_hash"] = hash_password(new_password)

    # 자기 계정에서는 status/default_role 수정하지 않도록 제거
    data.pop("status", None)
    data.pop("default_role", None)

    updated = user_crud.update_user(db, user=me, data=data)
    return UserResponse.model_validate(updated)


# ==============================
# Me: 프로필
# ==============================

@router.get("/my/profile", response_model=UserProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    profile = user_crud.get_profile(db, me.user_id)
    if not profile:
        # 프로필이 아직 없으면 404 반환
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return UserProfileResponse.model_validate(profile)


@router.patch("/my/profile", response_model=UserProfileResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    profile = user_crud.upsert_profile(db, user_id=me.user_id, data=data)
    return UserProfileResponse.model_validate(profile)


# ==============================
# Me: 보안 설정
# ==============================

@router.get("/my/security", response_model=UserSecuritySettingResponse)
def get_my_security(
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    sec = user_crud.get_security_setting(db, me.user_id)
    if not sec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="security settings not found")
    return UserSecuritySettingResponse.model_validate(sec)


@router.patch("/my/security", response_model=UserSecuritySettingResponse)
def update_my_security(
    payload: UserSecuritySettingUpdate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    sec = user_crud.upsert_security_setting(db, user_id=me.user_id, data=data)
    return UserSecuritySettingResponse.model_validate(sec)


# ==============================
# Me: 프라이버시 설정
# ==============================

@router.get("/my/privacy", response_model=UserPrivacySettingResponse)
def get_my_privacy(
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    privacy = user_crud.get_privacy_setting(db, me.user_id)
    if not privacy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="privacy settings not found")
    return UserPrivacySettingResponse.model_validate(privacy)


@router.patch("/my/privacy", response_model=UserPrivacySettingResponse)
def update_my_privacy(
    payload: UserPrivacySettingUpdate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    privacy = user_crud.upsert_privacy_setting(db, user_id=me.user_id, data=data)
    return UserPrivacySettingResponse.model_validate(privacy)


# ==============================
# Me: 로그인 세션 목록 (선택)
# ==============================

@router.get("/my/sessions", response_model=list[UserLoginSessionResponse])
def list_my_login_sessions(
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    현재 사용자 로그인 세션 목록 (최근 순, 상위 50개).
    Page 스키마를 따로 만들지 않고 단순 리스트로 반환.
    """
    rows, _ = user_crud.list_login_sessions(
        db,
        user_id=me.user_id,
        only_current=None,
        page=1,
        size=50,
    )
    return [UserLoginSessionResponse.model_validate(r) for r in rows]
