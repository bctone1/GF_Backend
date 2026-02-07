# service/partner/class_code.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from crud.partner import classes as classes_crud
from models.partner.course import Class, InviteCode
from schemas.partner.classes import ClassCreate
from service.partner.invite import _generate_unique_code, InviteServiceError

logger = logging.getLogger(__name__)


class ClassInviteServiceError(InviteServiceError):
    """클래스 초대코드 서비스 레벨 에러"""
    pass


def create_default_class_invite(
    db: Session,
    *,
    partner_id: int,
    class_id: int,
    created_by_partner_user_id: Optional[int] = None,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
) -> InviteCode:
    """
    이미 존재하는 class 에 대해 공유용 기본 학생 초대코드 1개 발급.
    - 이메일 발송 없음
    - target_role = 'student' 고정
    - status = 'active'
    """
    code = _generate_unique_code(db)

    try:
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
    except ValueError as exc:
        raise ClassInviteServiceError(str(exc)) from exc

    return invite


def create_class_with_default_invite(
    db: Session,
    *,
    partner_id: int,
    course_id: Optional[int],
    data: ClassCreate,
    created_by_partner_user_id: int,
) -> Class:
    """
    1) class 생성
    2) 해당 class 에 기본 초대코드 1개 자동 생성

    crud 레벨은 그대로 두고, 서비스에서 두 작업을 묶어준다.
    """
    # 1) 클래스 생성 (기존 crud 호출)
    clazz = classes_crud.create_class(
        db,
        partner_id=partner_id,
        course_id=course_id,
        name=data.name,
        description=data.description,
        status=data.status,
        start_at=data.start_at,
        end_at=data.end_at,
        capacity=data.capacity,
        timezone=data.timezone,
        location=data.location,
        online_url=data.online_url,
        invite_only=data.invite_only,
        primary_model_id=data.primary_model_id,
        allowed_model_ids=data.allowed_model_ids,
        budget_limit=data.budget_limit,
    )

    # 2) 기본 초대코드 1개 생성
    try:
        create_default_class_invite(
            db,
            partner_id=partner_id,
            class_id=clazz.id,
            created_by_partner_user_id=created_by_partner_user_id,
        )
    except ClassInviteServiceError as exc:
        logger.exception(
            "failed to create default invite for class %s: %s",
            clazz.id,
            exc,
        )
        # 여기서 raise 할지, 로그만 찍고 넘어갈지는 정책에 따라 결정

    return clazz

def list_class_invite_codes(
    db: Session,
    class_id: int,
    active_only: Optional[bool],
    limit: int,
    offset: int,
) -> tuple[list[InviteCode], int]:
    """
    특정 class 에 연결된 초대코드 목록 조회.

    - active_only=True 면 status='active' 만 필터링
    - limit/offset 으로 페이지네이션
    """
    # 기본 쿼리: 해당 class 의 모든 코드
    base_stmt = select(InviteCode).where(InviteCode.class_id == class_id)

    if active_only is True:
        base_stmt = base_stmt.where(InviteCode.status == "active")

    # total count
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    # rows
    stmt = (
        base_stmt
        .order_by(InviteCode.id.desc())  # 필요하면 created_at.desc() 등으로 변경
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total