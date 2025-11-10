# app/endpoints/partner/course.py
# app/endpoints/partner/course.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple

from core.deps import get_db, get_current_partner_admin
from schemas.partner.course import (
    CourseCreate, CourseUpdate, CourseResponse, CoursePage,
    ClassCreate, ClassUpdate, ClassResponse, ClassPage,
    InviteCodeCreate, InviteCodeUpdate, InviteCodeResponse, InviteCodePage,
)
from crud.partner import course as crud_course

router = APIRouter()


# ==============================
# Course CRUD
# ==============================
@router.get("", response_model=CoursePage)
def list_courses(
    partner_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    _=Depends(get_current_partner_admin),
):
    rows, total = crud_course.list_courses(
        db,
        partner_id=partner_id,
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "items": rows}


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    partner_id: int,
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.create_course(
        db,
        partner_id=partner_id,
        title=payload.title,
        code=payload.code,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
    )
    return obj


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    partner_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.get_course(db, course_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Course not found")
    return obj


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    partner_id: int,
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.update_course(
        db,
        course_id=course_id,
        title=payload.title,
        code=payload.code,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
    )
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Course not found")
    return obj


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    partner_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    ok = crud_course.delete_course(db, course_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Course not found")
    return None


# ==============================
# Class CRUD
# ==============================
@router.get("/{course_id}/classes", response_model=ClassPage)
def list_classes(
    partner_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    _=Depends(get_current_partner_admin),
):
    rows, total = crud_course.list_classes(
        db, course_id=course_id, status=status, limit=limit, offset=offset
    )
    return {"total": total, "items": rows}


@router.post("/{course_id}/classes", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(
    partner_id: int,
    course_id: int,
    payload: ClassCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.create_class(
        db,
        course_id=course_id,
        name=payload.name,
        section_code=payload.section_code,
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
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.get_class(db, class_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Class not found")
    return obj


@router.patch("/{course_id}/classes/{class_id}", response_model=ClassResponse)
def update_class(
    partner_id: int,
    course_id: int,
    class_id: int,
    payload: ClassUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.update_class(
        db,
        class_id=class_id,
        name=payload.name,
        section_code=payload.section_code,
        status=payload.status,
        start_at=payload.start_at,
        end_at=payload.end_at,
        capacity=payload.capacity,
        timezone=payload.timezone,
        location=payload.location,
        online_url=payload.online_url,
        invite_only=payload.invite_only,
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Class not found")
    return obj


@router.delete("/{course_id}/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    partner_id: int,
    course_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    ok = crud_course.delete_class(db, class_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Class not found")
    return None


# ==============================
# Invite Codes
# ==============================
@router.get("/{course_id}/classes/{class_id}/invites", response_model=InviteCodePage)
def list_invite_codes(
    partner_id: int,
    course_id: int,
    class_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    target_role: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    _=Depends(get_current_partner_admin),
):
    rows, total = crud_course.list_invite_codes(
        db,
        partner_id=partner_id,
        class_id=class_id,
        status=status,
        target_role=target_role,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "items": rows}


@router.post("/{course_id}/classes/{class_id}/invites", response_model=InviteCodeResponse)
def create_invite_code(
    partner_id: int,
    course_id: int,
    class_id: int,
    payload: InviteCodeCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    try:
        obj = crud_course.create_invite_code(
            db,
            partner_id=partner_id,
            class_id=class_id,
            code=payload.code,
            target_role=payload.target_role,
            expires_at=payload.expires_at,
            max_uses=payload.max_uses,
            status=payload.status or "active",
            created_by=payload.created_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return obj


@router.patch("/invites/{invite_code}", response_model=InviteCodeResponse)
def update_invite_code(
    partner_id: int,
    invite_code: str,
    payload: InviteCodeUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.update_invite_code(
        db,
        code=invite_code,
        target_role=payload.target_role,
        expires_at=payload.expires_at,
        max_uses=payload.max_uses,
        status=payload.status,
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Invite not found")
    return obj


@router.delete("/invites/{invite_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invite_code(
    partner_id: int,
    invite_code: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    ok = crud_course.delete_invite_code(db, code=invite_code)
    if not ok:
        raise HTTPException(status_code=404, detail="Invite not found")
    return None


# ==============================
# redeem instructor invite
# ==============================
@router.post("/redeem-invite", status_code=status.HTTP_200_OK)
def redeem_invite_and_attach_instructor(
    invite_code: str,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    초대코드 입력 → 유효성 검증 → instructor 등록
    """
    try:
        partner_id, class_id, role = crud_course.redeem_invite_and_attach_instructor(
            db,
            invite_code=invite_code,
            user_id=user_id,
        )
        return {"partner_id": partner_id, "class_id": class_id, "role": role}
    except crud_course.InviteError as e:
        raise HTTPException(status_code=400, detail=str(e))
