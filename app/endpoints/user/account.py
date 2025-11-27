# app/endpoints/user/account.py
from __future__ import annotations

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
from service.user import account_service

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
    EmailCodeSendRequest,
    EmailCodeSendResponse,
    EmailCodeVerifyRequest,
    EmailCodeVerifyResponse,
    PartnerPromotionRequestCreate,
    PartnerPromotionRequestResponse,
)
from schemas.partner.student import EnrollmentResponse


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
    """
    from service.email import send_email, EmailSendError

    email = payload.email.strip()

    # 6자리 숫자 코드 생성
    code = f"{randint(100000, 999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    data = {
        "email": email,
        "code": code,
        "exp": int(expires_at.timestamp()),
    }
    verification_token = sign_payload(data)

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
    - 항상 일반 member 로 생성 (partner_id / 역할 승격은 별도 플로우에서 처리)
    """
    return account_service.signup(db, payload)


@router.post("/user/login", response_model=AuthTokens)
def user_login(
    payload: LoginInput,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    이메일/비밀번호 기반 로그인.
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
    return UserResponse.model_validate(me)


@router.patch("/my", response_model=UserResponse)
def update_my_account(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> UserResponse:
    data = payload.model_dump(exclude_unset=True)

    if "password" in data:
        new_password = data.pop("password")
        data["password_hash"] = hash_password(new_password)

    # 클라이언트에서 민감 필드 변경 방지
    data.pop("status", None)
    data.pop("default_role", None)
    data.pop("partner_id", None)

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
    profile = account_service.update_my_profile(
        db=db,
        me_id=me.user_id,
        payload=payload,
    )
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
    rows, _ = user_crud.list_login_sessions(
        db,
        user_id=me.user_id,
        only_current=None,
        page=1,
        size=50,
    )
    return [UserLoginSessionResponse.model_validate(r) for r in rows]


# ==============================
# Partner / Instructor 승격 요청 생성
# ==============================
@router.post(
    "/partner-promotion-requests",
    response_model=PartnerPromotionRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_partner_promotion_request(
    payload: PartnerPromotionRequestCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    obj = account_service.create_partner_promotion_request(
        db=db,
        me=me,
        payload=payload,
    )
    return PartnerPromotionRequestResponse.model_validate(obj)


# ==============================
# Class: 클래스 초대코드 redeem
# ==============================
class InviteRedeemRequest(BaseModel):
    """
    로그인 후, 클래스 초대코드(6자리)만 입력하는 요청 스키마.
    - code: 클래스 초대코드
    - 학생 정보(이름/이메일/연락처)는 로그인 계정/프로필에서 가져옴
    """
    code: str


@router.post(
    "/class/invites/redeem",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def redeem_invite_code(
    payload: InviteRedeemRequest,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),  # 반드시 로그인 후 사용
):
    enrollment = account_service.redeem_class_invite_code(
        db=db,
        me=me,
        raw_code=payload.code,
    )
    return EnrollmentResponse.model_validate(enrollment)
