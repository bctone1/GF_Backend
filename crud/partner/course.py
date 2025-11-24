# crud/partner/course.py
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.partner.course import Course, Class, InviteCode
from models.partner.partner_core import PartnerUser  # partner_user 업서트용
from models.partner.student import Student, Enrollment
from crud.partner import student as student_crud


# ==============================
# Course
# ==============================
def get_course(db: Session, course_id: int) -> Optional[Course]:
    return db.get(Course, course_id)


def get_course_by_course_key(db: Session, org_id: int, course_key: str) -> Optional[Course]:
    stmt = select(Course).where(
        Course.org_id == org_id,
        Course.course_key == course_key,
    )
    return db.execute(stmt).scalars().first()


def list_courses(
    db: Session,
    org_id: int,
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_desc: bool = True,
) -> Tuple[List[Course], int]:
    conds = [Course.org_id == org_id]
    if status:
        conds.append(Course.status == status)
    if search:
        like = f"%{search}%"
        conds.append(or_(Course.title.ilike(like), Course.course_key.ilike(like)))

    base = select(Course).where(and_(*conds))
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar() or 0

    if order_desc:
        base = base.order_by(desc(Course.created_at))
    else:
        base = base.order_by(Course.created_at)

    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()
    return rows, total


def create_course(
    db: Session,
    *,
    org_id: int,
    title: str,
    course_key: str,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    description: Optional[str] = None,
) -> Course:
    obj = Course(
        org_id=org_id,
        title=title,
        course_key=course_key,
        status=status or "draft",
        start_date=start_date,
        end_date=end_date,
        description=description,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_course(
    db: Session,
    course_id: int,
    *,
    title: Optional[str] = None,
    course_key: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    description: Optional[str] = None,
) -> Optional[Course]:
    obj = db.get(Course, course_id)
    if not obj:
        return None

    if title is not None:
        obj.title = title
    if course_key is not None:
        obj.course_key = course_key
    if status is not None:
        obj.status = status
    if start_date is not None:
        obj.start_date = start_date
    if end_date is not None:
        obj.end_date = end_date
    if description is not None:
        obj.description = description

    db.commit()
    db.refresh(obj)
    return obj


def delete_course(db: Session, course_id: int) -> bool:
    res = db.execute(delete(Course).where(Course.id == course_id))
    db.commit()
    return res.rowcount > 0


# ==============================
# Class
# ==============================
def get_class(db: Session, class_id: int) -> Optional[Class]:
    return db.get(Class, class_id)


def list_classes(
    db: Session,
    course_id: int,
    *,
    status: Optional[str] = None,
    section_code: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_desc: bool = True,
) -> Tuple[List[Class], int]:
    """
    특정 course 에 속한 class 목록.
    (course 에 속하지 않는 class 는 별도 쿼리 필요)
    """
    conds = [Class.course_id == course_id]
    if status:
        conds.append(Class.status == status)
    if section_code:
        conds.append(Class.section_code == section_code)

    base = select(Class).where(and_(*conds))
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar() or 0

    base = base.order_by(desc(Class.created_at) if order_desc else Class.created_at)
    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()
    return rows, total


def create_class(
    db: Session,
    *,
    partner_id: int,
    course_id: Optional[int] = None,
    name: str,
    section_code: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    capacity: Optional[int] = None,
    timezone: Optional[str] = None,
    location: Optional[str] = None,
    online_url: Optional[str] = None,
    invite_only: Optional[bool] = None,
) -> Class:
    """
    - partner_id: 이 class 를 여는 강사(Partner) ID (필수)
    - course_id: course 에 소속되면 지정, 아니면 None
    """
    obj = Class(
        partner_id=partner_id,
        course_id=course_id,
        name=name,
        section_code=section_code,
        status=status or "planned",
        start_at=start_at,
        end_at=end_at,
        capacity=capacity,
        timezone=timezone or "UTC",
        location=location,
        online_url=online_url,
        invite_only=invite_only if invite_only is not None else False,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_class(
    db: Session,
    class_id: int,
    *,
    name: Optional[str] = None,
    section_code: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    capacity: Optional[int] = None,
    timezone: Optional[str] = None,
    location: Optional[str] = None,
    online_url: Optional[str] = None,
    invite_only: Optional[bool] = None,
) -> Optional[Class]:
    obj = db.get(Class, class_id)
    if not obj:
        return None

    if name is not None:
        obj.name = name
    if section_code is not None:
        obj.section_code = section_code
    if status is not None:
        obj.status = status
    if start_at is not None:
        obj.start_at = start_at
    if end_at is not None:
        obj.end_at = end_at
    if capacity is not None:
        obj.capacity = capacity
    if timezone is not None:
        obj.timezone = timezone
    if location is not None:
        obj.location = location
    if online_url is not None:
        obj.online_url = online_url
    if invite_only is not None:
        obj.invite_only = invite_only

    db.commit()
    db.refresh(obj)
    return obj


def delete_class(db: Session, class_id: int) -> bool:
    res = db.execute(delete(Class).where(Class.id == class_id))
    db.commit()
    return res.rowcount > 0

# ==============================
# InviteCode
# ==============================
class InviteError(Exception):
    pass


class InviteNotFound(InviteError):
    pass


class InviteExpired(InviteError):
    pass


class InviteDisabled(InviteError):
    pass


class InviteExhausted(InviteError):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------- 기본 CRUD ----------
def get_invite_by_id(db: Session, invite_id: int) -> Optional[InviteCode]:
    return db.get(InviteCode, invite_id)


def get_invite_code(db: Session, code: str) -> Optional[InviteCode]:
    stmt = select(InviteCode).where(InviteCode.code == code)
    return db.execute(stmt).scalars().first()


def list_invite_codes(
    db: Session,
    partner_id: int,
    *,
    class_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[InviteCode], int]:
    """
    partner 단위 초대코드 목록.
    - class_id 로 필터하면 특정 반의 코드만 조회
    - target_role 은 student-only 이므로 별도 필터 없음
    """
    conds = [InviteCode.partner_id == partner_id]
    if class_id is not None:
        conds.append(InviteCode.class_id == class_id)
    if status:
        conds.append(InviteCode.status == status)
    if search:
        conds.append(InviteCode.code.ilike(f"%{search}%"))

    base = (
        select(InviteCode)
        .where(and_(*conds))
        .order_by(desc(InviteCode.created_at))
    )
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar() or 0
    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()
    return rows, total


def create_invite_code(
    db: Session,
    *,
    partner_id: int,
    class_id: int,
    code: str,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
    status: str = "active",
    created_by: Optional[int] = None,
) -> InviteCode:
    """
    class 단위 학생 초대코드 생성.
    - partner_id: 코드 소유 파트너
    - class_id: 반드시 이 파트너가 가진 class 여야 함
    """
    # class 존재/소유권 검사
    clazz = db.get(Class, class_id)
    if not clazz:
        raise ValueError("class not found")
    if clazz.partner_id != partner_id:
        raise ValueError("partner_id mismatch with class")

    obj = InviteCode(
        partner_id=partner_id,
        class_id=class_id,
        code=code,
        target_role="student",  # student-only
        expires_at=expires_at,
        max_uses=max_uses,
        status=status,
        created_by=created_by,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_invite_code(
    db: Session,
    *,
    code: str,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
    status: Optional[str] = None,
) -> Optional[InviteCode]:
    """
    초대코드 속성 일부 수정.
    - target_role 은 DB 레벨에서 student-only 이므로 변경 불가
    """
    obj = get_invite_code(db, code)
    if not obj:
        return None

    if expires_at is not None:
        obj.expires_at = expires_at
    if max_uses is not None:
        obj.max_uses = max_uses
    if status is not None:
        obj.status = status

    db.commit()
    db.refresh(obj)
    return obj


def delete_invite_code(db: Session, *, code: str) -> bool:
    res = db.execute(delete(InviteCode).where(InviteCode.code == code))
    db.commit()
    return res.rowcount > 0


# ---------- 유효성 검사 & 사용 처리 ----------
def check_invite_usable(inv: InviteCode, *, now: Optional[datetime] = None) -> None:
    now = now or _now_utc()
    if inv.status == "disabled":
        raise InviteDisabled("invite disabled")
    if inv.expires_at and now >= inv.expires_at:
        raise InviteExpired("invite expired")
    if inv.max_uses is not None and inv.used_count >= inv.max_uses:
        raise InviteExhausted("invite exhausted")


def increment_invite_use(
    db: Session,
    *,
    code: str,
    now: Optional[datetime] = None,
) -> InviteCode:
    """
    used_count를 원자적으로 +1. 만료/용량 초과는 갱신 실패로 처리.
    """
    now = now or _now_utc()

    stmt = (
        update(InviteCode)
        .where(
            InviteCode.code == code,
            InviteCode.status == "active",
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at > now),
            or_(InviteCode.max_uses.is_(None), InviteCode.used_count < InviteCode.max_uses),
        )
        .values(used_count=InviteCode.used_count + 1)
        .returning(InviteCode)
    )
    row = db.execute(stmt).first()
    if not row:
        inv = get_invite_code(db, code)
        if not inv:
            raise InviteNotFound("invite not found")
        check_invite_usable(inv, now=now)
        raise InviteError("concurrent update failed")
    db.commit()
    return row[0]


# ==============================
# PartnerUser upsert (강사 연결)
# ==============================
def upsert_partner_user_role(
    db: Session,
    *,
    partner_id: int,
    user_id: int,
    role: str = "partner",
    is_active: bool = True,
) -> PartnerUser:
    """
    (partner_id, user_id) 멱등 업서트. role은 갱신.
    partner.partner_users 유니크 제약( partner_id + user_id ) 전제.
    """
    ins = pg_insert(PartnerUser).values(
        partner_id=partner_id,
        user_id=user_id,
        role=role,
        is_active=is_active,
        updated_at=func.now(),
    )
    do_update = ins.on_conflict_do_update(
        index_elements=[PartnerUser.partner_id, PartnerUser.user_id],
        set_={
            "role": role,
            "is_active": is_active,
            "updated_at": func.now(),
        },
    ).returning(PartnerUser)
    row = db.execute(do_update).first()
    db.commit()
    return row[0]


# ==============================
# redeem partner invite (강사 초대) - 현재 설계에서는 미사용
# ==============================
def redeem_invite_and_attach_instructor(
    db: Session,
    *,
    invite_code: str,
    user_id: int,
) -> Tuple[int, Optional[int], str]:
    """
    [Deprecated]
    - 현재 InviteCode 는 student-only, class 기반 초대코드로 사용.
    - 파트너 승격은 supervisor 프로모션 플로우 등을 통해 처리해야 함.
    """
    raise InviteError(
        "partner invites are no longer supported on InviteCode; "
        "use the supervisor promotion flow instead."
    )


# ==============================
# redeem student invite
# ==============================
def redeem_student_invite_and_enroll(
    db: Session,
    *,
    invite_code: str,
    email: Optional[str],
    full_name: str,
    primary_contact: Optional[str] = None,
) -> Tuple[Student, Enrollment, InviteCode]:
    """
    학생 초대코드 검증 → 사용량 증가 → Student 생성/조회 + Enrollment 멱등 등록

    - target_role == "student" 인 코드만 허용
    - InviteCode.class_id 가 필수 (어느 반에 등록할지)
    - student_crud.ensure_enrollment_for_invite 를 사용해
      (partner_id, email) 기준으로 학생/수강을 멱등 처리
    반환: (student, enrollment, invite)
    """
    inv = get_invite_code(db, invite_code)
    if not inv:
        raise InviteNotFound("invite not found")

    # student 전용 코드만 허용 (DB에서도 강제)
    if inv.target_role != "student":
        raise InviteError("invite is not for student")

    check_invite_usable(inv)

    # 사용량 증가 (원자적)
    inv = increment_invite_use(db, code=invite_code)

    # 학생 초대는 어느 반에 붙일지 알아야 해서 class_id 필수
    if inv.class_id is None:
        raise InviteError("student invite must be associated with a class")

    # 학생 + 수강 멱등 등록
    student, enrollment = student_crud.ensure_enrollment_for_invite(
        db,
        partner_id=inv.partner_id,
        class_id=inv.class_id,
        invite_code_id=inv.id,
        email=email,
        full_name=full_name,
        primary_contact=primary_contact,
    )

    return student, enrollment, inv
