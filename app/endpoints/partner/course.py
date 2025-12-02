# app/endpoints/partner/course.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from schemas.partner.course import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CoursePage,
)
from crud.partner import course as crud_course
from models.partner.partner_core import Partner

router = APIRouter()


def _require_org_id(current_partner: Partner) -> int:
    org_id = getattr(current_partner, "org_id", None)
    if org_id is None:
        raise HTTPException(status_code=400, detail="org_id not found for current partner")
    return org_id


# ==============================
# Course CRUD
# ==============================
@router.get(
    "",
    response_model=CoursePage,
    summary="모든 코스 조회",
)
def list_courses(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_partner: Partner = Depends(get_current_partner_user),
):
    org_id = _require_org_id(current_partner)

    rows, total = crud_course.list_courses(
        db=db,
        org_id=org_id,
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )

    page = offset // limit + 1 if limit > 0 else 1
    size = limit

    items = [CourseResponse.model_validate(r) for r in rows]
    return {
        "total": total,
        "items": items,
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
    payload: CourseCreate,
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
):
    org_id = _require_org_id(current_partner)

    obj = crud_course.create_course(
        db,
        org_id=org_id,
        title=payload.title,
        course_key=payload.course_key,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
    )
    return CourseResponse.model_validate(obj)


@router.get(
    "/{course_id}",
    response_model=CourseResponse,
    summary="코스 상세 조회",
)
def get_course(
    course_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
):
    org_id = _require_org_id(current_partner)

    obj = crud_course.get_course(db, course_id)
    if not obj or obj.org_id != org_id:
        raise HTTPException(status_code=404, detail="Course not found")
    return CourseResponse.model_validate(obj)


@router.patch(
    "/{course_id}",
    response_model=CourseResponse,
    summary="코스 수정",
)
def update_course(
    course_id: int = Path(..., ge=1),
    payload: CourseUpdate = ...,
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
):
    org_id = _require_org_id(current_partner)

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
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Course not found")
    return CourseResponse.model_validate(obj)


@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="코스 삭제",
)
def delete_course(
    course_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
):
    org_id = _require_org_id(current_partner)

    obj = crud_course.get_course(db, course_id)
    if not obj or obj.org_id != org_id:
        raise HTTPException(status_code=404, detail="Course not found")

    ok = crud_course.delete_course(db, course_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Course not found")
    return None
