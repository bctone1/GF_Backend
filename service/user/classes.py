# service/user/classes.py
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.partner.student import Student, Enrollment
from models.partner.course import Class, Course
from models.partner.partner_core import Org, Partner


def list_my_classes_raw(
    db: Session,
    *,
    user_id: int,
    status_in: Optional[Sequence[str]] = None,   # Enrollment 기준
    limit: int = 50,
    offset: int = 0,
):
    student_ids_subq = (
        select(Student.id)
        .where(Student.user_id == user_id)
        .subquery()
    )

    stmt = (
        select(
            Enrollment,
            Class,
            Course,
            Org,
            Partner,
        )
        .join(Class, Class.id == Enrollment.class_id)
        .join(Student, Student.id == Enrollment.student_id)
        .outerjoin(Course, Course.id == Class.course_id)   # 코스 없는 단독 클래스 고려
        .outerjoin(Org, Org.id == Course.org_id)
        .join(Partner, Partner.id == Class.partner_id)
        .where(Enrollment.student_id.in_(select(student_ids_subq.c.id)))
        .order_by(Enrollment.enrolled_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if status_in:
        stmt = stmt.where(Enrollment.status.in_(status_in))

    rows = db.execute(stmt).all()
    return rows
