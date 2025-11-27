# service/user/account_service.py
from __future__ import annotations

from typing import Dict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crud.user import account as user_crud
from crud.partner import student as student_crud
from crud.partner import course as course_crud

from core.security import hash_password, verify_password, issue_tokens

from models.user.account import UserProfile, AppUser
from models.supervisor.core import PartnerPromotionRequest

from schemas.user.account import (
    UserCreate,
    UserResponse,
    LoginInput,
    AuthTokens,
    UserProfileUpdate,
    PartnerPromotionRequestCreate,
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


# ==============================
# Partner / Instructor 승격 요청
# ==============================
def create_partner_promotion_request(
    db: Session,
    *,
    me: AppUser,
    payload: PartnerPromotionRequestCreate,
) -> PartnerPromotionRequest:
    """
    파트너/강사 승격 요청 생성 서비스 레이어
    - 이미 is_partner=True 이면 거절
    - pending 상태 요청이 이미 있으면 거절
    - partner_promotion_requests 레코드 생성
    """
    if getattr(me, "is_partner", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="already_partner",
        )

    existing = (
        db.execute(
            select(PartnerPromotionRequest).where(
                PartnerPromotionRequest.user_id == me.user_id,
                PartnerPromotionRequest.status == "pending",
            )
        )
        .scalars()
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="already_pending_promotion_request",
        )

    obj = PartnerPromotionRequest(
        user_id=me.user_id,
        name=payload.name,
        email=payload.email,
        org_name=payload.org_name,
        edu_category=payload.edu_category,
        target_role=payload.target_role,
    )

    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="promotion_request_conflict",
        )

    db.refresh(obj)
    return obj


# ==============================
# Class 초대코드 redeem
# ==============================
def redeem_class_invite_code(
    db: Session,
    *,
    me: AppUser,
    raw_code: str,
):
    """
    클래스 초대코드(6자리)로:
    - (로그인한 유저 정보 기준으로) 학생 생성/조회 (partner 스코프)
    - 수강 등록(enrollment) 생성 (멱등)
    - 초대코드 used 처리
    - 잘못된/만료 코드 처리
    - 동일 학생 중복 등록 방지
    """
    # 1) 코드 정규화
    code = raw_code.strip().upper()
    if len(code) != 6:
        raise HTTPException(status_code=400, detail="invalid_code_format")

    # 2) 초대코드 조회 + 유효성 검사
    invite = course_crud.get_invite_for_redeem(db, code=code)
    if not invite:
        raise HTTPException(status_code=400, detail="invalid_or_expired_code")

    # (옵션) class 존재 여부 정도만 체크
    class_obj = course_crud.get_class(db, invite.class_id)
    if not class_obj:
        raise HTTPException(status_code=400, detail="class_not_found")

    # 3) Student 용 이메일/이름/연락처 결정
    student_email = me.email
    if not student_email:
        raise HTTPException(status_code=400, detail="email_required")

    profile = user_crud.get_profile(db, me.user_id)

    student_full_name = (
        (profile.full_name if profile else None)
        or getattr(me, "full_name", None)
        or student_email
    )

    primary_contact = (
        profile.phone_number
        if profile and getattr(profile, "phone_number", None)
        else None
    )

    # 4) 학생 생성/조회 + 수강등록 멱등 처리
    #    Student.partner_id = invite.partner_id (초대코드 발급한 강사 기준 스코프)
    student, enrollment = student_crud.ensure_enrollment_for_invite(
        db,
        partner_id=invite.partner_id,
        class_id=invite.class_id,
        invite_code_id=invite.id,
        email=student_email,
        full_name=student_full_name,
        primary_contact=primary_contact,
    )

    # 5) 초대코드 사용 처리
    course_crud.mark_invite_used(
        db,
        invite_id=invite.id,
        student_id=student.id,
    )

    return enrollment
