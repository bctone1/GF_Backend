# app/endpoints/partner/course.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from schemas.partner.course import (
    CourseCreate, CourseUpdate, CourseResponse, CoursePage,
    ClassCreate, ClassUpdate, ClassResponse, ClassPage,
    InviteCodeResponse, InviteCodePage,
)
from crud.partner import course as crud_course
from service.partner import class_code as class_code_service

router = APIRouter()


# ==============================
# Course CRUD (org 기준)
# ==============================
@router.get("", response_model=CoursePage)
def list_courses(
    org_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _=Depends(get_current_partner_user),
):
    rows, total = crud_course.list_courses(
        db,
        org_id=org_id,
        status=status,
        search=search,
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


@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="코스 생성",
)
def create_course(
    org_id: int,
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.create_course(
        db,
        org_id=org_id,
        title=payload.title,
        course_key=payload.course_key,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
        # LLM 설정
        primary_model_id=getattr(payload, "primary_model_id", None),
        allowed_model_ids=getattr(payload, "allowed_model_ids", None),
    )
    return obj


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    org_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.get_course(db, course_id)
    if not obj or obj.org_id != org_id:
        raise HTTPException(status_code=404, detail="Course not found")
    return obj


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    org_id: int,
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.get_course(db, course_id)
    if not obj or obj.org_id != org_id:
        raise HTTPException(status_code=404, detail="Course not found")

    obj = crud_course.update_course(
        db,
        course_id=course_id,
        title=payload.title,
        course_key=payload.course_key,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
        primary_model_id=getattr(payload, "primary_model_id", None),
        allowed_model_ids=getattr(payload, "allowed_model_ids", None),
    )
    return obj


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    org_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.get_course(db, course_id)
    if not obj or obj.org_id != org_id:
        raise HTTPException(status_code=404, detail="Course not found")

    ok = crud_course.delete_course(db, course_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Course not found")
    return None


# ==============================
# Class CRUD (1 class : 1 partner)
# ==============================
@router.get("/{course_id}/classes", response_model=ClassPage)
def list_classes(
    partner_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    _=Depends(get_current_partner_user),
):
    """
    여기서는 course_id 기준 전체 class 조회.
    (partner_id 로 필터링하지 않고, 단순히 코스에 속한 반 목록)
    """
    rows, total = crud_course.list_classes(
        db,
        course_id=course_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    page = offset // limit + 1 if limit > 0 else 1
    size = limit
    return {"total": total, "items": rows, "page": page, "size": size}


@router.post(
    "/{course_id}/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
    summary="강의생성/초대코드 발급",
)
def create_class(
    partner_id: int,
    course_id: int,
    payload: ClassCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    class 생성 + 기본 초대코드 1개 자동 생성.
    - Class.partner_id = path 의 partner_id (PartnerUser.id)
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


@router.get("/{course_id}/classes/{class_id}", response_model=ClassResponse)
def get_class(
    partner_id: int,
    course_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.get_class(db, class_id)
    if not obj or obj.course_id != course_id or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")
    return obj


@router.patch("/{course_id}/classes/{class_id}", response_model=ClassResponse)
def update_class(
    partner_id: int,
    course_id: int,
    class_id: int,
    payload: ClassUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.get_class(db, class_id)
    if not obj or obj.course_id != course_id or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    obj = crud_course.update_class(
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


@router.delete("/{course_id}/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    partner_id: int,
    course_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.get_class(db, class_id)
    if not obj or obj.course_id != course_id or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    ok = crud_course.delete_class(db, class_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Class not found")
    return None


# ==============================
# Class Invite Codes (초대코드 조회)
# ==============================
@router.get(
    "/{course_id}/classes/{class_id}/invite-codes",
    response_model=InviteCodePage,
)
def list_class_invite_codes(
    partner_id: int,
    course_id: int,
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

    - URL: GET /partners/{partner_id}/courses/{course_id}/classes/{class_id}/invite-codes
    - 권한: 현재 로그인한 partner 기준으로 class 소속 확인
    """
    # 1) class 소속 검증 (course / partner 둘 다 체크)
    klass = crud_course.get_class(db, class_id)
    if not klass or klass.course_id != course_id or klass.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Class not found")

    # 2) 초대코드 목록 조회 (service 레이어 사용)
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
