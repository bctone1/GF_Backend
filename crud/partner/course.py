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


def get_course_by_course_key(
    db: Session,
    org_id: int,
    course_key: str,
) -> Optional[Course]:
    stmt = select(Course).where(
        Course.org_id == org_id,
        Course.course_key == course_key,
    )
    return db.execute(stmt).scalars().first()


def list_courses(
    db: Session,
    org_id: Optional[int] = None,
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_desc: bool = True,
) -> Tuple[List[Course], int]:
    """
    org_id가 None이면 전체 코스 조회.
    """
    conds = []
    if org_id is not None:
        conds.append(Course.org_id == org_id)
    if status:
        conds.append(Course.status == status)
    if search:
        like = f"%{search}%"
        conds.append(
            or_(
                Course.title.ilike(like),
                Course.course_key.ilike(like),
            )
        )

    base = select(Course)
    if conds:
        base = base.where(and_(*conds))

    total = (
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar()
        or 0
    )

    if order_desc:
        base = base.order_by(desc(Course.created_at))
    else:
        base = base.order_by(Course.created_at)

    rows = db.execute(
        base.limit(limit).offset(offset)
    ).scalars().all()
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
    """
    Course는 이제 LLM 설정을 가지지 않는다.
    (LLM은 Class 단위에서 설정)
    """
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
    """
    Course에는 더 이상 primary_model_id / allowed_model_ids 없음.
    """
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
