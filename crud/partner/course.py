# crud/partner/course.py
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.orm import Session, selectinload

from models.partner.course import Course, Class, InviteCode


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
    primary_model_id: Optional[int] = None,
    allowed_model_ids: Optional[List[int]] = None,
) -> Course:
    """
    allowed_model_ids 가 None 이면 DB 기본값([]::jsonb) 사용.
    """
    extra: dict = {}
    if allowed_model_ids is not None:
        extra["allowed_model_ids"] = allowed_model_ids

    obj = Course(
        org_id=org_id,
        title=title,
        course_key=course_key,
        status=status or "draft",
        start_date=start_date,
        end_date=end_date,
        description=description,
        primary_model_id=primary_model_id,
        **extra,
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
    primary_model_id: Optional[int] = None,
    allowed_model_ids: Optional[List[int]] = None,
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
    if primary_model_id is not None:
        obj.primary_model_id = primary_model_id
    if allowed_model_ids is not None:
        obj.allowed_model_ids = allowed_model_ids

    db.commit()
    db.refresh(obj)
    return obj


def delete_course(db: Session, course_id: int) -> bool:
    res = db.execute(delete(Course).where(Course.id == course_id))
    db.commit()
    return res.rowcount > 0

