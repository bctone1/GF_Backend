# app/endpoints/partner/course.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from schemas.partner.course import (
    CourseCreate, CourseUpdate, CourseResponse, CoursePage,
    ClassCreate, ClassUpdate, ClassResponse, ClassPage,
)
from crud.partner import course as crud_course

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


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/{course_id}/classes", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(
    partner_id: int,
    course_id: int,
    payload: ClassCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = crud_course.create_class(
        db,
        partner_id=partner_id,
        course_id=course_id,
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
