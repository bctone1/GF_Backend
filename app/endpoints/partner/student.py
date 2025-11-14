# app/endpoints/partner/student.py
from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.deps import get_db, get_current_partner_admin, get_current_partner_member
from crud.partner import student as student_crud

from schemas.partner.student import (
    StudentCreate, StudentUpdate, StudentResponse,
    EnrollmentCreate, EnrollmentUpdate, EnrollmentResponse,
)

router = APIRouter()

# ==============================
# Students
# ==============================
@router.get("", response_model=List[StudentResponse])
def list_students(
    partner_id: int,
    status_: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, description="이름/이메일/연락처 검색"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_member),
):
    return student_crud.list_students(
        db,
        partner_id=partner_id,
        status=status_,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    partner_id: int,
    data: StudentCreate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    try:
        return student_crud.create_student(
            db,
            partner_id=partner_id,
            full_name=data.full_name,
            email=data.email,
            status=data.status or "active",
            primary_contact=data.primary_contact,
            notes=data.notes,
        )
    except student_crud.StudentConflict as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    partner_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_member),
):
    obj = student_crud.get_student(db, student_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")
    return obj


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(
    partner_id: int,
    student_id: int,
    data: StudentUpdate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    try:
        updated = student_crud.update_student(db, student_id, **data.model_dump(exclude_unset=True))
    except student_crud.StudentConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not updated or updated.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")
    return updated


@router.post("/{student_id}/deactivate", response_model=StudentResponse)
def deactivate_student(
    partner_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    """
    비활성화 시킴(종료와 다름)
    """
    updated = student_crud.deactivate_student(db, student_id)
    if not updated or updated.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")
    return updated


@router.post("/{student_id}/archive", response_model=StudentResponse)
def archive_student(
    partner_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    updated = student_crud.archive_student(db, student_id)
    if not updated or updated.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")
    return updated


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    partner_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    obj = student_crud.get_student(db, student_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")
    ok = student_crud.delete_student(db, student_id)
    if not ok:
        raise HTTPException(status_code=404, detail="student not found")
    return None


# ==============================
# Enrollments
# ==============================
@router.get("/{student_id}/enrollments", response_model=List[EnrollmentResponse])
def list_enrollments_for_student(
    partner_id: int,
    student_id: int,
    status_: Optional[str] = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_member),
):
    # 소속 확인
    st = student_crud.get_student(db, student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")
    return student_crud.list_enrollments_by_student(
        db,
        student_id=student_id,
        status=status_,
        limit=limit,
        offset=offset,
    )


@router.post("/{student_id}/enrollments", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_student(
    partner_id: int,
    student_id: int,
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    # 소속 확인
    st = student_crud.get_student(db, student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")

    # 멱등 확인
    existing = student_crud.find_enrollment(db, class_id=data.class_id, student_id=student_id)
    if existing:
        return existing
    try:
        return student_crud.enroll_student(
            db,
            class_id=data.class_id,
            student_id=student_id,
            invite_code_id=data.invite_code_id,
            status=data.status or "active",
            progress_percent=float(data.progress_percent or 0),
            final_grade=data.final_grade,
        )
    except student_crud.EnrollmentConflict as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
def update_enrollment(
    partner_id: int,
    enrollment_id: int,
    data: EnrollmentUpdate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    obj = student_crud.get_enrollment(db, enrollment_id)
    if not obj:
        raise HTTPException(status_code=404, detail="enrollment not found")
    # 경계 체크: 학생 소속 파트너 일치
    st = student_crud.get_student(db, obj.student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="enrollment not found")

    updated = student_crud.update_enrollment(db, enrollment_id, **data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="enrollment not found")
    return updated


@router.post("/enrollments/{enrollment_id}/complete", response_model=EnrollmentResponse)
def complete_enrollment(
    partner_id: int,
    enrollment_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    obj = student_crud.get_enrollment(db, enrollment_id)
    if not obj:
        raise HTTPException(status_code=404, detail="enrollment not found")
    st = student_crud.get_student(db, obj.student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="enrollment not found")

    done = student_crud.mark_completed(db, enrollment_id)
    if not done:
        raise HTTPException(status_code=404, detail="enrollment not found")
    return done


@router.post("/enrollments/{enrollment_id}/drop", response_model=EnrollmentResponse)
def drop_enrollment(
    partner_id: int,
    enrollment_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    obj = student_crud.get_enrollment(db, enrollment_id)
    if not obj:
        raise HTTPException(status_code=404, detail="enrollment not found")
    st = student_crud.get_student(db, obj.student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="enrollment not found")

    dropped = student_crud.drop_enrollment(db, enrollment_id)
    if not dropped:
        raise HTTPException(status_code=404, detail="enrollment not found")
    return dropped


@router.delete("/enrollments/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment(
    partner_id: int,
    enrollment_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_admin),
):
    obj = student_crud.get_enrollment(db, enrollment_id)
    if not obj:
        raise HTTPException(status_code=404, detail="enrollment not found")
    st = student_crud.get_student(db, obj.student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="enrollment not found")

    ok = student_crud.delete_enrollment(db, enrollment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="enrollment not found")
    return None
