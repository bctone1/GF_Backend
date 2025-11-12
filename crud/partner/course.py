# crud/partner/course.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, update, delete, func, and_, or_, literal, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.partner.course import Course, Class, ClassInstructor, InviteCode
from models.partner.partner_core import PartnerUser  # partner_user 업서트용
from sqlalchemy.dialects.postgresql import insert as pg_insert


# ==============================
# Course
# ==============================
def get_course(db: Session, course_id: int) -> Optional[Course]:
    return db.get(Course, course_id)


def get_course_by_course_key(db: Session, partner_id: int, course_key: str) -> Optional[Course]:
    stmt = select(Course).where(Course.partner_id == partner_id, Course.course_key == course_key)
    return db.execute(stmt).scalars().first()


def list_courses(
    db: Session,
    partner_id: int,
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_desc: bool = True,
) -> Tuple[List[Course], int]:
    conds = [Course.partner_id == partner_id]
    if status:
        conds.append(Course.status == status)
    if search:
        like = f"%{search}%"
        conds.append(or_(Course.title.ilike(like), Course.course_key.ilike(like)))

    base = select(Course).where(and_(*conds))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0

    if order_desc:
        base = base.order_by(desc(Course.created_at))
    else:
        base = base.order_by(Course.created_at)

    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()
    return rows, total


def create_course(
    db: Session,
    *,
    partner_id: int,
    title: str,
    course_key: str,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    description: Optional[str] = None,
) -> Course:
    obj = Course(
        partner_id=partner_id,
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
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
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
    conds = [Class.course_id == course_id]
    if status:
        conds.append(Class.status == status)
    if section_code:
        conds.append(Class.section_code == section_code)

    base = select(Class).where(and_(*conds))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    base = base.order_by(desc(Class.created_at) if order_desc else Class.created_at)
    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()
    return rows, total


def create_class(
    db: Session,
    *,
    course_id: int,
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
    obj = Class(
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
# ClassInstructor
# ==============================
def list_class_instructors(db: Session, class_id: int) -> List[ClassInstructor]:
    stmt = select(ClassInstructor).where(ClassInstructor.class_id == class_id).order_by(ClassInstructor.id)
    return db.execute(stmt).scalars().all()


def add_class_instructor(db: Session, *, class_id: int, partner_user_id: int, role: str = "assistant") -> ClassInstructor:
    obj = ClassInstructor(class_id=class_id, partner_user_id=partner_user_id, role=role)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 이미 존재하면 그대로 반환
        stmt = select(ClassInstructor).where(
            ClassInstructor.class_id == class_id,
            ClassInstructor.partner_user_id == partner_user_id,
        )
        exist = db.execute(stmt).scalars().first()
        if exist:
            return exist
        raise
    db.refresh(obj)
    return obj


def update_class_instructor_role(db: Session, *, class_instructor_id: int, role: str) -> Optional[ClassInstructor]:
    obj = db.get(ClassInstructor, class_instructor_id)
    if not obj:
        return None
    obj.role = role
    db.commit()
    db.refresh(obj)
    return obj


def remove_class_instructor(db: Session, *, class_id: int, partner_user_id: int) -> bool:
    res = db.execute(
        delete(ClassInstructor).where(
            ClassInstructor.class_id == class_id,
            ClassInstructor.partner_user_id == partner_user_id,
        )
    )
    db.commit()
    return res.rowcount > 0


# ==============================
# InviteCode
# ==============================
def get_invite_code(db: Session, code: str) -> Optional[InviteCode]:
    stmt = select(InviteCode).where(InviteCode.code == code)
    return db.execute(stmt).scalars().first()


def list_invite_codes(
    db: Session,
    partner_id: int,
    *,
    class_id: Optional[int] = None,
    status: Optional[str] = None,
    target_role: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[InviteCode], int]:
    conds = [InviteCode.partner_id == partner_id]
    if class_id is not None:
        conds.append(InviteCode.class_id == class_id)
    if status:
        conds.append(InviteCode.status == status)
    if target_role:
        conds.append(InviteCode.target_role == target_role)
    if search:
        conds.append(InviteCode.code.ilike(f"%{search}%"))

    base = select(InviteCode).where(and_(*conds)).order_by(desc(InviteCode.created_at))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()
    return rows, total


def create_invite_code(
    db: Session,
    *,
    partner_id: int,
    code: str,
    target_role: str = "student",  # "instructor"|"student"
    class_id: Optional[int] = None,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
    status: str = "active",
    created_by: Optional[int] = None,
) -> InviteCode:
    # class_id 제공 시 partner 일치성 검사
    if class_id is not None:
        clazz = db.get(Class, class_id)
        if not clazz:
            raise ValueError("class not found")
        course = db.get(Course, clazz.course_id)
        if not course or course.partner_id != partner_id:
            raise ValueError("partner_id mismatch with class")

    obj = InviteCode(
        partner_id=partner_id,
        class_id=class_id,
        code=code,
        target_role=target_role,
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
    target_role: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
    status: Optional[str] = None,
) -> Optional[InviteCode]:
    obj = get_invite_code(db, code)
    if not obj:
        return None
    if target_role is not None:
        obj.target_role = target_role
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


# ==============================
# InviteCode Redemption Helpers
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


def check_invite_usable(inv: InviteCode, *, now: Optional[datetime] = None) -> None:
    now = now or _now_utc()
    if inv.status == "disabled":
        raise InviteDisabled("invite disabled")
    if inv.expires_at and now >= inv.expires_at:
        raise InviteExpired("invite expired")
    if inv.max_uses is not None and inv.used_count >= inv.max_uses:
        raise InviteExhausted("invite exhausted")


def increment_invite_use(db: Session, *, code: str, now: Optional[datetime] = None) -> InviteCode:
    """
    used_count를 원자적으로 +1. 만료/용량 초과는 갱신 실패로 처리.
    """
    now = now or _now_utc()

    # 조건부 업데이트: 유효한 경우에만 +1
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
        # 실패 원인 식별을 위해 현재 상태 조회
        inv = get_invite_code(db, code)
        if not inv:
            raise InviteNotFound("invite not found")
        check_invite_usable(inv, now=now)  # 여기서 적절한 예외 발생
        # 상태는 active지만 동시경쟁 등으로 실패한 경우
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
    role: str = "instructor",
    is_active: bool = True,
) -> PartnerUser:
    """
    (partner_id, user_id) 멱등 업서트. role은 갱신.
    partner.partner_users의 유니크 제약(예상: partner_id, user_id)을 전제로 함.
    """
    ins = pg_insert(PartnerUser).values(
        partner_id=partner_id,
        user_id=user_id,
        role=role,
        is_active=is_active,
        updated_at=func.now(),
    )
    # on conflict: set role, is_active, updated_at
    do_update = ins.on_conflict_do_update(
        index_elements=[PartnerUser.partner_id, PartnerUser.user_id],
        set_=dict(role=role, is_active=is_active, updated_at=func.now()),
    ).returning(PartnerUser)
    row = db.execute(do_update).first()
    db.commit()
    return row[0]


# ==============================
# redeem instructor invite
# ==============================
def redeem_invite_and_attach_instructor(
    db: Session,
    *,
    invite_code: str,
    user_id: int,
) -> Tuple[int, Optional[int], str]:
    """
    초대코드 검증 → 사용량 증가 → 파트너 강사 연결(멱등)
    반환: (partner_id, class_id, target_role)
    서비스 계층에서 토큰 재발급/세션 리프레시 처리.
    """
    # invite_codes 테이블에서 해당 code를 조회
    inv = get_invite_code(db, invite_code)
    if not inv:
        raise InviteNotFound("invite not found")

    # 초대 코드 유효성 검증(조건불만족하면 예외 던짐)
    check_invite_usable(inv)

    # 초대 코드 사용량 증가시킴
    inv = increment_invite_use(db, code=invite_code)

    # 초대코드가 강사용이면(instructor) partner_users 업서트
    if inv.target_role == "instructor":
        upsert_partner_user_role(db, partner_id=inv.partner_id, user_id=user_id, role="instructor")

    return inv.partner_id, inv.class_id, inv.target_role
