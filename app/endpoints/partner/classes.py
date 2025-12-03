# app/endpoints/partner/classes.py
from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session, selectinload

from core.deps import get_db, get_current_partner_user

# 스키마: 코스/클래스/초대코드가 같이 있는 모듈
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
from models.partner.course import Class as ClassModel


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
    partner_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    course_id: Optional[int] = Query(
        None,
        description="특정 코스에 속한 강의만 보고 싶으면 지정",
    ),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _=Depends(get_current_partner_user),
):
    """
    - 기본: partner_id 기준으로 내가 만든 모든 class 조회
    - course_id 가 있으면 해당 course 에 속한 class 만 필터링
    """
    conds: List = [ClassModel.partner_id == partner_id]
    if course_id is not None:
        conds.append(ClassModel.course_id == course_id)
    if status:
        conds.append(ClassModel.status == status)

    base = (
        select(ClassModel)
        .options(selectinload(ClassModel.invite_codes))  # 초대코드까지 같이 로드
        .where(and_(*conds))
    )

    total = (
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar()
        or 0
    )

    base = base.order_by(desc(ClassModel.created_at))
    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()

    page = offset // limit + 1 if limit > 0 else 1
    size = limit

    items = [ClassResponse.model_validate(r) for r in rows]

    return {
        "total": total,
        "items": items,
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
    partner_id: int = Path(..., ge=1),
    payload: ClassCreate = ...,
    db: Session = Depends(get_db),
    course_id: Optional[int] = Query(
        None,
        description="이 강의를 특정 course에 소속시키고 싶으면 지정 (없으면 독립 class)",
    ),
    current_partner_user=Depends(get_current_partner_user),
):
    """
    class 생성 + 기본 초대코드 1개 자동 생성.

    - Class.partner_id = path 의 partner_id (Partner.id)
    - course_id 는 Query 로 받되, 없으면 payload.course_id 사용
    - payload 안의 primary_model_id / allowed_model_ids 로 LLM 설정
    - 기본 초대코드는 student 초대용으로 1개 발급

    model_catalog 에 없는 모델 id 를 넘기면 400 에러 반환.
    """
    # Query 우선, 없으면 body 의 course_id 사용
    effective_course_id = course_id if course_id is not None else payload.course_id

    try:
        obj = class_code_service.create_class_with_default_invite(
            db=db,
            partner_id=partner_id,
            course_id=effective_course_id,
            data=payload,
            # 초대코드 생성자: 실제 로그인한 partner_user의 id 사용
            created_by_partner_user_id=current_partner_user.id,
        )
    except ValueError as e:
        # 예: model_catalog 에 없는 모델 id 등
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return ClassResponse.model_validate(obj)


@router.get(
    "/{class_id}",
    response_model=ClassResponse,
    summary="단일 강의 조회",
)
def get_class(
    partner_id: int = Path(..., ge=1),
    class_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_classes.get_class(db, class_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    return ClassResponse.model_validate(obj)


@router.patch(
    "/{class_id}",
    response_model=ClassResponse,
    summary="강의 수정",
)
def update_class(
    partner_id: int = Path(..., ge=1),
    class_id: int = Path(..., ge=1),
    payload: ClassUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_classes.get_class(db, class_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    try:
        obj = crud_classes.update_class(
            db,
            class_id=class_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            start_at=payload.start_at,
            end_at=payload.end_at,
            capacity=payload.capacity,
            timezone=payload.timezone,
            location=payload.location,
            online_url=payload.online_url,
            invite_only=payload.invite_only,
            course_id=payload.course_id,
            # LLM 설정
            primary_model_id=payload.primary_model_id,
            allowed_model_ids=payload.allowed_model_ids,
        )
    except ValueError as e:
        # 예: model_catalog 에 없는 모델 id 등
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if not obj:
        raise HTTPException(status_code=404, detail="Class not found")

    return ClassResponse.model_validate(obj)


@router.delete(
    "/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="강의 삭제",
)
def delete_class(
    partner_id: int = Path(..., ge=1),
    class_id: int = Path(..., ge=1),
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
    partner_id: int = Path(..., ge=1),
    class_id: int = Path(..., ge=1),
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

    items = [InviteCodeResponse.model_validate(r) for r in rows]

    return {
        "total": total,
        "items": items,
        "page": page,
        "size": size,
    }
