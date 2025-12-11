# app/endpoints/user/account.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import randint
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
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
from models.partner.student import Student, Enrollment
from models.partner.course import Class, Course
from models.partner.partner_core import Org, Partner

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
from schemas.partner.student import EnrollmentResponse, StudentClassPage, StudentClassResponse
from schemas.enums import EnrollmentStatus


router = APIRouter()


# ==============================
# Me: 내 강의 리스트
# ==============================
@router.get(
    "/classes",
    response_model=StudentClassPage,
    summary="내 강의 리스트",
)
def list_my_classes(
    status: Optional[EnrollmentStatus] = Query(
        None,
        description="수강 상태 필터 (예: active | completed | inactive | dropped)",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    현재 로그인한 유저 기준 '내 강의' 리스트.

    1) students.user_id == me.user_id 인 Student들을 모두 찾고
    2) 해당 student_id들에 대한 Enrollment를 찾은 뒤
    3) Class / Course / Org / Partner 를 조인해서 카드형 정보로 반환.
    """

    # 1) 현재 유저에 매핑된 학생들 (여러 기관/파트너 소속일 수 있음)
    student_ids_subq = (
        select(Student.id)
        .where(Student.user_id == me.user_id)
        .subquery()
    )

    # 학생 레코드가 아예 없으면 바로 빈 페이지 반환
    total_students = db.execute(
        select(func.count()).select_from(student_ids_subq)
    ).scalar() or 0
    if total_students == 0:
        return StudentClassPage(
            total=0,
            items=[],
            page=1,
            size=limit,
        )

    # 2) Enrollment ↔ Class ↔ Course ↔ Org ↔ Partner 조인
    base = (
        select(Enrollment, Class, Course, Org, Partner)
        .join(Class, Class.id == Enrollment.class_id)
        .join(Student, Student.id == Enrollment.student_id)
        .outerjoin(Course, Course.id == Class.course_id)
        .outerjoin(Org, Org.id == Course.org_id)
        .join(Partner, Partner.id == Class.partner_id)
        .where(Enrollment.student_id.in_(select(student_ids_subq.c.id)))
    )

    # 기본: active + completed 만 노출
    if status is None:
        base = base.where(Enrollment.status.in_(["active", "completed"]))
    else:
        base = base.where(Enrollment.status == status.value)

    # 3) total / page 계산
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar() or 0

    rows = db.execute(
        base.order_by(Enrollment.enrolled_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items: List[StudentClassResponse] = []
    for enr, cls, course, org, partner in rows:
        items.append(
            StudentClassResponse(
                enrollment_id=enr.id,
                class_id=cls.id,
                class_title=getattr(cls, "name", ""),
                primary_model_id=getattr(cls, "primary_model_id", None),
                allowed_model_ids=(getattr(cls, "allowed_model_ids", None) or []),

                course_title=(course.title if course is not None else None),
                org_name=(getattr(org, "name", None) if org is not None else None),

                teacher_name=(getattr(partner, "full_name", None) or getattr(partner, "email", None)),

                class_start_at=getattr(cls, "start_at", None),
                class_end_at=getattr(cls, "end_at", None),

                enrollment_status=enr.status,
                enrolled_at=enr.enrolled_at,
                completed_at=enr.completed_at,
                last_activity_at=None,
            )
        )

    page = offset // limit + 1 if limit > 0 else 1

    return StudentClassPage(
        total=total,
        items=items,
        page=page,
        size=limit,
    )

# ==============================
# Me: 내 수강 삭제(수강 취소)
# ==============================
@router.delete(
    "/class/enrollments/{enrollment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="내 수강 삭제(수강 취소)",
)
def delete_my_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    ok = user_crud.delete_enrollment_for_user(
        db,
        enrollment_id=enrollment_id,
        user_id=me.user_id,
    )
    if not ok:
        # 내 수강이 아니거나 존재하지 않으면 404
        raise HTTPException(status_code=404, detail="enrollment not found")
    return None



# ==============================
# Auth: 이메일 코드 발송 / 인증
# ==============================
@router.post(
    "/email/send-code",
    response_model=EmailCodeSendResponse,
    summary="가입 전 인증 코드 발송",
)
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


@router.post(
    "/email/verify-code",
    response_model=EmailCodeVerifyResponse,
    summary="이메일 코드 인증",
)
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
@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
def user_signup(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    """
    기본 사용자 회원가입.
    - 항상 일반 member 로 생성 (partner_id / 역할 승격은 별도 플로우에서 처리)
    """
    return account_service.signup(db, payload)


@router.post(
    "/login",
    response_model=AuthTokens,
    summary="이메일/비밀번호 로그인",
)
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
    summary="강사 권한 요청",
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
    summary="초대코드 수강 등록",
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


