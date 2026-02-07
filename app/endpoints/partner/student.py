# app/endpoints/partner/student.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from core.deps import get_db, get_current_partner_user, get_current_user
from crud.partner import student as student_crud
from crud.partner.activity import create_activity_event

from schemas.partner.student import (
    StudentCreate, StudentUpdate, StudentResponse,
    EnrollmentCreate, EnrollmentUpdate, EnrollmentResponse,
    StudentDetailResponse, StudentStatsResponse,
)
from models.user.account import AppUser
from models.partner.student import Student, Enrollment
from models.partner.course import Class, Course
from models.partner.partner_core import Org, Partner
from schemas.enums import EnrollmentStatus
from schemas.partner.student import StudentClassResponse, StudentClassPage
from service.partner.student_summary import list_students_with_stats

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
    _=Depends(get_current_partner_user),
):
    return student_crud.list_students(
        db,
        partner_id=partner_id,
        status=status_,
        q=q,
        limit=limit,
        offset=offset,
    )


# 혹시몰라주석 강사가 직접 학생을 생성하는 API인데 현재 미사용(PM에서 논의 완전삭제도 가능)
"""
@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    partner_id: int,
    data: StudentCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
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
"""


@router.get(
    "/stats",
    response_model=StudentStatsResponse,
    summary="학생 요약 통계",
)
def get_student_stats(
    partner_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
):
    """전체 학생 수, 활성/완료 학생 수, 참여율."""
    # status별 학생 수
    status_rows = db.execute(
        select(Student.status, func.count(Student.id))
        .where(Student.partner_id == partner_id)
        .group_by(Student.status)
    ).all()
    status_map = {r[0]: r[1] for r in status_rows}

    total = sum(status_map.values())
    active = status_map.get("active", 0)

    # completed: 해당 partner의 class에 enrollment status='completed'인 학생 수
    class_ids_subq = (
        select(Class.id).where(Class.partner_id == partner_id)
    ).subquery()

    completed = db.execute(
        select(func.count(func.distinct(Enrollment.student_id)))
        .where(
            Enrollment.class_id.in_(select(class_ids_subq.c.id)),
            Enrollment.status == "completed",
        )
    ).scalar_one()

    engagement = Decimal(str(active * 100 / total)) if total > 0 else Decimal("0")

    return StudentStatsResponse(
        total_students=total,
        active_students=active,
        completed_students=completed,
        engagement_rate=engagement.quantize(Decimal("0.1")),
    )


@router.get(
    "/detail",
    response_model=list[StudentDetailResponse],
    summary="학생 목록 + 통계 상세",
)
def list_students_detail(
    partner_id: int = Path(..., ge=1),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, description="이름/이메일/연락처 검색"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
):
    """학생 목록 — 수강 정보, 대화 수, 비용, 최근 활동 포함."""
    return list_students_with_stats(
        db,
        partner=current_partner,
        status_filter=status_filter,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    partner_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
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
    _=Depends(get_current_partner_user),
):
    try:
        updated = student_crud.update_student(
            db,
            student_id,
            **data.model_dump(exclude_unset=True),
        )
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
    _=Depends(get_current_partner_user),
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
    _=Depends(get_current_partner_user),
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
    _=Depends(get_current_partner_user),
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
    _=Depends(get_current_partner_user),
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


@router.post(
    "/{student_id}/enrollments",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def enroll_student(
    partner_id: int,
    student_id: int,
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
):
    # 소속 확인
    st = student_crud.get_student(db, student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="student not found")

    # 멱등 확인 (동일 class에 이미 등록된 경우 그대로 반환)
    existing = student_crud.find_enrollment(
        db,
        class_id=data.class_id,
        student_id=student_id,
    )
    if existing:
        return existing

    try:
        enrollment = student_crud.enroll_student(
            db,
            class_id=data.class_id,
            student_id=student_id,
            invite_code_id=data.invite_code_id,
            status=data.status or "active",
        )
    except student_crud.EnrollmentConflict as e:
        raise HTTPException(status_code=409, detail=str(e))

    # activity 발행 (student_joined)
    create_activity_event(
        db,
        partner_id=current_partner.org_id,
        event_type="student_joined",
        title=f"{st.full_name}님이 수강 등록",
        class_id=data.class_id,
        student_id=student_id,
    )
    db.commit()

    return enrollment


@router.patch("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
def update_enrollment(
    partner_id: int,
    enrollment_id: int,
    data: EnrollmentUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = student_crud.get_enrollment(db, enrollment_id)
    if not obj:
        raise HTTPException(status_code=404, detail="enrollment not found")

    # 경계 체크: 학생 소속 파트너 일치
    st = student_crud.get_student(db, obj.student_id)
    if not st or st.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="enrollment not found")

    updated = student_crud.update_enrollment(
        db,
        enrollment_id,
        **data.model_dump(exclude_unset=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="enrollment not found")
    return updated


@router.post("/enrollments/{enrollment_id}/complete", response_model=EnrollmentResponse)
def complete_enrollment(
    partner_id: int,
    enrollment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
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
    _=Depends(get_current_partner_user),
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
    _=Depends(get_current_partner_user),
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

