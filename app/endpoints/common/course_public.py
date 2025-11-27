# app/endpoints/common/course_public.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.deps import get_db
from schemas.partner.course import CoursePage
from crud.partner import course as crud_course

router = APIRouter()

@router.get("", response_model=CoursePage, summary="전체 코스조회")
def list_public_courses(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = crud_course.list_courses(
        db=db,
        org_id=None,  # ← 전체 org 대상
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )

    page = offset // limit + 1 if limit > 0 else 1

    return {
        "total": total,
        "items": rows,
        "page": page,
        "size": limit,
    }
