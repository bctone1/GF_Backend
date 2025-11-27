# service/partner/invite.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import secrets
from sqlalchemy.orm import Session

from crud.partner import course as course_crud
from crud.partner import classes as classes_crud
from crud.user import account as user_crud
from models.partner.course import InviteCode
from service.email import send_email, EmailSendError
import logging

logger = logging.getLogger(__name__)


def create_default_class_invite(
    db: Session,
    *,
    partner_id: int,
    class_id: int,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
    created_by_partner_user_id: Optional[int] = None,
) -> InviteCode:
    """
    클래스 생성 후, 공유용 기본 초대코드 1개 발급용
    - 이메일 발송 없음
    - target_role 은 항상 'student'
    """
    code = _generate_unique_code(db)

    invite = classes_crud.create_invite_code(
        db,
        partner_id=partner_id,
        code=code,
        target_role="student",
        class_id=class_id,
        expires_at=expires_at,
        max_uses=max_uses,
        status="active",
        created_by=created_by_partner_user_id,
    )
    return invite




# ==============================
# Service 레벨 에러
# ==============================
class InviteServiceError(Exception):
    pass

class InviteCodeGenerationError(InviteServiceError):
    pass

# ==============================
# 초대 발송 결과 DTO
# ==============================
@dataclass
class InviteSendResult:
    invite: InviteCode
    invite_url: str
    email: str
    is_existing_user: bool
    email_sent: bool


# ==============================
# 초대코드 생성 (secure 랜덤 base32 스타일)
# ==============================
INVITE_CODE_LENGTH = 6  # GF3M5P
SAFE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # I,O,0,1 헷갈린거


def generate_invite_code(length: int = INVITE_CODE_LENGTH) -> str:
    """
    초대코드 난수 생성
    - secrets 기반 crypto-safe
    - base32 계열 알파벳에서 샘플링
    """
    return "".join(secrets.choice(SAFE_ALPHABET) for _ in range(length))


def _generate_unique_code(db: Session, max_attempts: int = 5) -> str:
    """
    DB 중복 체크까지 포함해서 유니크 코드 생성
    """
    for _ in range(max_attempts):
        code = generate_invite_code()
        if classes_crud.get_invite_code(db, code) is None:
            return code
    raise InviteCodeGenerationError("failed to generate unique invite code")


# ==============================
# URL 빌더
# ==============================
def build_invite_url(code: str) -> str:
    """
    초대 URL 생성 추후 작업
    - 실제로는 FRONTEND_BASE_URL + /invite/{code} 로 확장 예정
    """
    return f"/invite/{code}"


# ==============================
# 이메일 템플릿
#   - 신규 가입자용
#   - 기존 유저용
# ==============================
def render_new_user_invite_email(
    *,
    invite_url: str,
    code: str,
) -> tuple[str, str]:
    """
    아직 GrowFit에 가입하지 않은 사용자용 템플릿
    """
    subject = "[GrowFit] AI 실습 과정 초대 코드 안내"

    body = f"""안녕하세요.

GrowFit AI 플랫폼 초대 메일입니다.

아래 초대 링크를 통해 회원가입을 완료하면,
자동으로 해당 과정/클래스에 수강 등록됩니다.

  1) 아래 링크로 접속

  2) 회원가입 진행

  3) 로그인 후 초대코드가 자동으로 적용됩니다.

초대 링크: {invite_url}
초대 코드: {code}

※ 초대코드는 다른 사람과 공유하지 말아 주세요.

감사합니다.
GrowFit 운영팀 드림
"""
    return subject, body


def render_existing_user_invite_email(
    *,
    invite_url: str,
    code: str,
) -> tuple[str, str]:
    """
    이미 GrowFit 계정이 있는 사용자용 템플릿
    """
    subject = "[GrowFit] AI 실습 과정 초대가 도착했습니다"

    body = f"""안녕하세요.

GrowFit AI 실습 플랫폼에서 새로운 과정 초대코드가 도착했습니다.

아래 초대 링크를 클릭하시면,
로그인 후 해당 과정/클래스에 바로 참여하실 수 있습니다.

초대 링크: {invite_url}
초대 코드: {code}

※ 이미 로그인된 상태라면, 링크 접속 시 바로 초대가 적용될 수 있습니다.

감사합니다.

추가로 문의 사항 있을시, 담당 강사에 별도의 연락 부탁드립니다

GrowFit 운영팀 드림
"""
    return subject, body


def send_invite_email(
    *,
    to_email: str,
    invite_url: str,
    code: str,
    is_existing_user: bool,
) -> bool:
    if is_existing_user:
        subject, body = render_existing_user_invite_email(
            invite_url=invite_url,
            code=code,
        )
    else:
        subject, body = render_new_user_invite_email(
            invite_url=invite_url,
            code=code,
        )

    try:
        send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            is_html=False,
        )
        return True
    except EmailSendError as e:
        logger.exception("failed to send invite email: %s", e)
        return False

# ==============================
# 공통: 초대코드 생성 + 이메일 발송
# ==============================
def create_and_send_invite(
    db: Session,
    *,
    partner_id: int,
    email: str,
    class_id: Optional[int],
    target_role: str,
    expires_at: Optional[datetime],
    max_uses: Optional[int],
    created_by_partner_user_id: Optional[int] = None,
) -> InviteSendResult:
    """
    1) user.users 에서 이메일 존재 여부 확인
    2) 초대코드 난수 생성 (충돌 체크)
    3) partner.invite_codes 생성
    4) 이메일 템플릿 선택(신규/기가입) 후 발송
    """
    app_user = user_crud.get_by_email(db, email)
    is_existing_user = app_user is not None

    code = _generate_unique_code(db)
    try:
        invite = classes_crud.create_invite_code(
            db,
            partner_id=partner_id,
            code=code,
            target_role=target_role or "student",
            class_id=class_id,
            expires_at=expires_at,
            max_uses=max_uses,
            status="active",
            created_by=created_by_partner_user_id,
        )
    except ValueError as e:
        raise InviteServiceError(str(e))

    invite_url = build_invite_url(invite.code)
    email_sent = send_invite_email(
        to_email=email,
        invite_url=invite_url,
        code=invite.code,
        is_existing_user=is_existing_user,
    )

    return InviteSendResult(
        invite=invite,
        invite_url=invite_url,
        email=email,
        is_existing_user=is_existing_user,
        email_sent=email_sent,
    )


def resend_invite(
    db: Session,
    *,
    partner_id: int,
    invite_id: int,
    email: str,
) -> InviteSendResult:
    """
    이미 생성된 invite_id를 기준으로 이메일 재발송
    """
    invite = classes_crud.get_invite_by_id(db, invite_id)
    if not invite or invite.partner_id != partner_id:
        raise InviteServiceError("invite not found")

    app_user = user_crud.get_by_email(db, email)
    is_existing_user = app_user is not None

    invite_url = build_invite_url(invite.code)
    email_sent = send_invite_email(
        to_email=email,
        invite_url=invite_url,
        code=invite.code,
        is_existing_user=is_existing_user,
    )

    return InviteSendResult(
        invite=invite,
        invite_url=invite_url,
        email=email,
        is_existing_user=is_existing_user,
        email_sent=email_sent,
    )


def assign_invite_by_email(
    db: Session,
    *,
    partner_id: int,
    email: str,
    class_id: Optional[int],
    target_role: str,
    expires_at: Optional[datetime],
    max_uses: Optional[int],
    created_by_partner_user_id: Optional[int] = None,
) -> InviteSendResult:
    """
    이메일 기준 자동 분기:
    - 가입 여부 확인
    - 초대코드 생성
    - 템플릿 분기 후 이메일 발송
    """
    return create_and_send_invite(
        db,
        partner_id=partner_id,
        email=email,
        class_id=class_id,
        target_role=target_role,
        expires_at=expires_at,
        max_uses=max_uses,
        created_by_partner_user_id=created_by_partner_user_id,
    )
