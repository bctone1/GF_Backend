# app/endpoints/partner/course.py
from __future__ import annotations

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_admin
from schemas.partner.course import (
    CourseCreate, CourseUpdate, CourseResponse, CoursePage,
    ClassCreate, ClassUpdate, ClassResponse, ClassPage,
    InviteCodeCreate, InviteCodeUpdate, InviteCodeResponse, InviteCodePage,
    InviteSendRequest, InviteAssignRequest, InviteResendRequest, InviteSendResponse,
)
from crud.partner import course as crud_course
from service.partner import invite as invite_service



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
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
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

    # limit/offset → page/size 계산
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
    partner_id: int,
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = crud_course.create_course(
        db,
        partner_id=partner_id,
        title=payload.title,
        course_key=payload.course_key,
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
        course_key=payload.course_key,
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
    page = offset // limit + 1
    size = limit
    return {"total": total, "items": rows, "page": page, "size": size}


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
# Invite Codes CRUD
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
    page = offset // limit + 1
    size = limit
    return {"total": total, "items": rows, "page": page, "size": size}


@router.post("/{course_id}/classes/{class_id}/invites", response_model=InviteCodeResponse)
def create_invite_code(
    partner_id: int,
    course_id: int,
    class_id: int,
    payload: InviteCodeCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_partner_admin),
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
            created_by=getattr(current_admin,"id",None),
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


# redeem instructor invite
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


# POST /invites/send : 초대코드 생성 + 이메일 발송
@router.post(
    "/invites/send",
    response_model=InviteSendResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="partner_create_and_send_invite",
)
def create_and_send_invite(
    partner_id: int,
    payload: InviteSendRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    """
    파트너가 특정 이메일로 초대코드를 생성해서 즉시 발송
    """
    try:
        result = invite_service.create_and_send_invite(
            db,
            partner_id=partner_id,
            email=payload.email,
            class_id=payload.class_id,
            target_role=payload.target_role,
            expires_at=payload.expires_at,
            max_uses=payload.max_uses,
        )
    except invite_service.InviteServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return InviteSendResponse(
        invite_id=result.invite.id,
        code=result.invite.code,
        invite_url=result.invite_url,
        email=result.email,
        is_existing_user=result.is_existing_user,
        email_sent=result.email_sent,
    )



# POST /invites/{id}/send : 기존 invite 재발송 :RESEND
@router.post(
    "/invites/{invite_id}/send",
    response_model=InviteSendResponse,
    status_code=status.HTTP_200_OK,
    operation_id="partner_resend_invite",
)
def resend_invite(
    partner_id: int,
    invite_id: int,
    payload: InviteResendRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    """
    이미 생성된 초대코드를 다른(또는 같은) 이메일로 재발송
    """
    try:
        result = invite_service.resend_invite(
            db,
            partner_id=partner_id,
            invite_id=invite_id,
            email=payload.email,
        )
    except invite_service.InviteServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return InviteSendResponse(
        invite_id=result.invite.id,
        code=result.invite.code,
        invite_url=result.invite_url,
        email=result.email,
        is_existing_user=result.is_existing_user,
        email_sent=result.email_sent,
    )

# POST /invites/assign : 가입 여부 확인 + 초대코드 생성 + 발송
@router.post(
    "/invites/assign",
    response_model=InviteSendResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="partner_assign_invite_by_email",
)
def assign_invite_by_email(
    partner_id: int,
    payload: InviteAssignRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    """
    이메일 기준으로:
    - 이미 가입된 user 인지 확인
    - 초대코드 생성
    - 템플릿은 service에서 신규/기가입 분기
    """
    try:
        result = invite_service.assign_invite_by_email(
            db,
            partner_id=partner_id,
            email=payload.email,
            class_id=payload.class_id,
            target_role=payload.target_role,
            expires_at=payload.expires_at,
            max_uses=payload.max_uses,
        )
    except invite_service.InviteServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return InviteSendResponse(
        invite_id=result.invite.id,
        code=result.invite.code,
        invite_url=result.invite_url,
        email=result.email,
        is_existing_user=result.is_existing_user,
        email_sent=result.email_sent,
    )

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


# ==============================
# redeem student invite
# ==============================
@router.post("/invites/redeem-student", status_code=status.HTTP_200_OK)
def redeem_student_invite_and_enroll(
    invite_code: str,
    full_name: str,
    email: Optional[str] = None,
    primary_contact: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    학생 초대코드 입력 → 유효성 검증 → Student 생성/조회 + 수강 등록 멱등 처리
    - target_role == 'student' 인 초대코드만 허용
    - InviteCode.class_id 필수
    """
    try:
        student, enrollment, inv = crud_course.redeem_student_invite_and_enroll(
            db,
            invite_code=invite_code,
            email=email,
            full_name=full_name,
            primary_contact=primary_contact,
        )
    except crud_course.InviteError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "student_id": student.id,
        "enrollment_id": enrollment.id,
        "partner_id": inv.partner_id,
        "class_id": inv.class_id,
        "invite_code": inv.code,
    }
