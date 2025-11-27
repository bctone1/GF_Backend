# app/endpoints/partner/classes.py
from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from schemas.partner.classes import (
    ClassCreate,
    ClassUpdate,
    ClassResponse,
    ClassPage,
    InviteCodeResponse,
    InviteCodePage,
)

from crud.partner import classes as crud_classes
from service.partner import class_code as class_code_service
from models.partner.course import Class  # partner_id 기준 리스트용

router = APIRouter()


# ==============================
# Class CRUD (1 class : 1 partner)
# ==============================

@router.get(
    "",
    response_model=ClassPage,
    summary="내 강의 목록 (partner 기준, course_id 옵션)",
)
def list_classes_for_partner(
    partner_id: int,
    db: Session = Depends(get_db),
    course_id: Optional[int] = Query(
        None, description="특정 코스에 속한 강의만 보고 싶으면 지정"
    ),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    _=Depends(get_current_partner_user),
):
    """
    - 기본: partner_id 기준으로 내가 만든 모든 class 조회
    - course_id 가 있으면 해당 course 에 속한 class 만 필터링
    """
    conds: List = [Class.partner_id == partner_id]
    if course_id is not None:
        conds.append(Class.course_id == course_id)
    if status:
        conds.append(Class.status == status)

    base = select(Class).where(and_(*conds))
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar() or 0

    base = base.order_by(desc(Class.created_at))
    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()

    page = offset // limit + 1 if limit > 0 else 1
    size = limit

    return {
        "total": total,
        "items": rows,
        "page": page,
        "size": size,
    }


@router.post(
    "",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
    summary="강의 생성 + 기본 초대코드 발급",
)
def create_class(
    partner_id: int,
    payload: ClassCreate,
    db: Session = Depends(get_db),
    course_id: Optional[int] = Query(
        None,
        description="이 강의를 특정 course에 소속시키고 싶으면 지정 (없으면 독립 class)",
    ),
    _=Depends(get_current_partner_user),
):
    """
    class 생성 + 기본 초대코드 1개 자동 생성.
    - Class.partner_id = path 의 partner_id (PartnerUser.id)
    - course_id 는 Query 로 받아서 course 소속 여부만 결정
    - 기본 초대코드는 student 초대용으로 1개 발급
    """
    obj = class_code_service.create_class_with_default_invite(
        db,
        partner_id=partner_id,
        course_id=course_id,
        data=payload,
        created_by_partner_user_id=partner_id,
    )
    return obj


@router.get(
    "/{class_id}",
    response_model=ClassResponse,
    summary="단일 강의 조회",
)
def get_class(
    partner_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_classes.get_class(db, class_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    # obj.invite_codes 까지 포함해서 ClassResponse로 변환됨
    return obj


@router.patch(
    "/{class_id}",
    response_model=ClassResponse,
    summary="강의 수정",
)
def update_class(
    partner_id: int,
    class_id: int,
    payload: ClassUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_classes.get_class(db, class_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    obj = crud_classes.update_class(
        db,
        class_id=class_id,
        name=payload.name,
        description=getattr(payload, "description", None),
        status=payload.status,
        start_at=payload.start_at,
        end_at=payload.end_at,
        capacity=payload.capacity,
        timezone=payload.timezone,
        location=payload.location,
        online_url=payload.online_url,
        invite_only=payload.invite_only,
    )
    return obj


@router.delete(
    "/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="강의 삭제",
)
def delete_class(
    partner_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_classes.get_class(db, class_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    ok = crud_classes.delete_class(db, class_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Class not found")
    return None


# ==============================
# Class Invite Codes (초대코드 조회)
# ==============================
@router.get(
    "/{class_id}/invite-codes",
    response_model=InviteCodePage,
    summary="강의별 초대코드 조회",
)
def list_class_invite_codes(
    partner_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    active_only: Optional[bool] = Query(
        None,
        description="True일 경우 활성(미만료) 코드만 필터링",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _=Depends(get_current_partner_user),
):
    """
    특정 class 에 연결된 초대코드 목록 조회.
    - URL: GET /partner/{partner_id}/classes/{class_id}/invite-codes
    - 권한: 현재 로그인한 partner 기준으로 class 소속 확인
    """
    # class 가 내 것인지 먼저 확인
    klass = crud_classes.get_class(db, class_id)
    if not klass or klass.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    rows, total = class_code_service.list_class_invite_codes(
        db=db,
        class_id=class_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    page = offset // limit + 1 if limit > 0 else 1
    size = limit

    return {
        "total": total,
        "items": rows,
        "page": page,
        "size": size,
    }
