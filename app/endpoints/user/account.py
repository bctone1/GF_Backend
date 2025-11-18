# app/endpoints/user/account.py
from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta, timezone
from random import randint

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.deps import get_db, get_current_user
from core.security import (
    hash_password,
    sign_payload,
    verify_signed_payload,
)

from crud.user import account as user_crud
from models.user.account import AppUser
from schemas.user.account import (
    LoginInput, AuthTokens, UserCreate, UserUpdate,
    UserResponse, UserProfileUpdate, UserProfileResponse, UserSecuritySettingUpdate,
    UserSecuritySettingResponse, UserPrivacySettingUpdate,
    UserPrivacySettingResponse,  UserLoginSessionResponse,
    EmailCodeSendRequest, EmailCodeSendResponse,
    EmailCodeVerifyRequest, EmailCodeVerifyResponse,
)

from service.user import account_service
from service.email import send_email, EmailSendError

router = APIRouter()

# ==============================
# Auth: 이메일 코드 발송 / 인증
# ==============================
@router.post("/user/email/send-code", response_model=EmailCodeSendResponse)
def send_email_code(
    payload: EmailCodeSendRequest,
):
    """
    회원가입 전 이메일 인증코드 발송.
    - DB 저장 없이, email/code/exp 를 서명한 verification_token 으로만 관리
    - 실제 메일은 service.email.send_email 사용
    """
    email = payload.email.strip()

    # 6자리 숫자 코드 생성
    code = f"{randint(100000, 999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    data = {
        "email": email,
        "code": code,
        "exp": int(expires_at.timestamp()),
    }
    # email + code + exp 를 서명해서 프론트에 전달
    verification_token = sign_payload(data)

    # 실제 메일 발송
    subject = "[GrowFit] 이메일 인증 코드"
    body = (
        f"GrowFit 회원가입 이메일 인증 코드입니다.\n\n"
        f"코드: {code}\n\n"
        f"유효 시간: 10분\n\n"
        f"페이지에서 위 코드를 입력해 주세요."
    )

    try:
        send_email(
            to_email=email,
            subject=subject,
            body=body,
            is_html=False,
        )
    except EmailSendError as e:
        # 메일 전송 실패 시 에러 반환
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to send verification email",
        ) from e

    return EmailCodeSendResponse(email=email, verification_token=verification_token)


@router.post("/user/email/verify-code", response_model=EmailCodeVerifyResponse)
def verify_email_code(
    payload: EmailCodeVerifyRequest,
):
    """
    이메일 + 코드 + verification_token 을 받아서 검증.
    성공 시 회원가입에서 사용할 email_verified_token 발급.
    """
    # 서명/위변조/만료 검증
    try:
        data = verify_signed_payload(payload.verification_token)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid verification token")

    # 1) 이메일 일치
    if data.get("email") != payload.email:
        raise HTTPException(status_code=400, detail="email mismatch")

    # 2) 코드 일치
    if data.get("code") != payload.code:
        raise HTTPException(status_code=400, detail="invalid code")

    # 3) 만료 확인
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if data.get("exp", 0) < now_ts:
        raise HTTPException(status_code=400, detail="code expired")

    # 이 시점에서 "이 이메일은 인증됨" 이라는 토큰 발급 (회원가입에서 사용)
    email_verified_token = sign_payload(
        {
            "email": payload.email,
            "verified": True,
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
        }
    )

    return EmailCodeVerifyResponse(email=payload.email, email_verified_token=email_verified_token)


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
    - email 인증 토큰(email_verified_token) 검증
    - 실제 생성은 service.user.account_service.signup 에 위임
    """
    # 1) 이메일 인증 토큰 확인
    if not getattr(payload, "email_verified_token", None):
        raise HTTPException(status_code=400, detail="email verification required")

    try:
        vdata = verify_signed_payload(payload.email_verified_token)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid email_verified_token")

    # 이메일/플래그/만료 확인
    if vdata.get("email") != payload.email or not vdata.get("verified"):
        raise HTTPException(status_code=400, detail="email not verified")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if vdata.get("exp", 0) < now_ts:
        raise HTTPException(status_code=400, detail="verification token expired")

    # 2) 실제 회원 생성은 서비스 레이어에 위임
    return account_service.signup(db, payload)


@router.post("/user/login", response_model=AuthTokens)
def user_login(
    payload: LoginInput,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    이메일/비밀번호 기반 로그인.
    - 실제 로직은 service.user.account_service.login 에 위임
    """
    client = request.client
    meta = {
        "device_name": None,
        "ip_address": client.host if client else None,
        "location": None,
        "user_agent": request.headers.get("user-agent"),
    }
    return account_service.login(db, payload, meta)


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
# Me: 로그인 세션 목록
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
