# service/partner/student_summary.py
"""학생 목록 + 통계 요약 서비스."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.partner.partner_core import Partner
from models.partner.course import Class
from models.partner.student import Student, Enrollment
from models.partner.usage import UsageEvent

from crud.partner import student as student_crud
from schemas.partner.student import StudentDetailResponse, StudentEnrollmentInfo


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def list_students_with_stats(
    db: Session,
    *,
    partner: Partner,
    status_filter: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[StudentDetailResponse]:
    """학생 목록을 수강/사용 통계와 함께 반환한다."""
    org_id = partner.org_id

    # 1) Student 목록
    students = student_crud.list_students(
        db,
        partner_id=partner.id,
        status=status_filter,
        q=q,
        limit=limit,
        offset=offset,
    )

    if not students:
        return []

    student_ids = [s.id for s in students]

    # 2) 일괄 쿼리 (N+1 방지)

    # enrollments
    enrollment_rows = db.execute(
        select(
            Enrollment.student_id,
            Enrollment.id,
            Enrollment.class_id,
            Class.name,
            Enrollment.status,
        )
        .join(Class, Enrollment.class_id == Class.id)
        .where(Enrollment.student_id.in_(student_ids))
    ).all()

    enrollment_map: dict[int, list[StudentEnrollmentInfo]] = {}
    for row in enrollment_rows:
        sid = row[0]
        info = StudentEnrollmentInfo(
            enrollment_id=row[1],
            class_id=row[2],
            class_name=row[3],
            enrollment_status=row[4],
        )
        enrollment_map.setdefault(sid, []).append(info)

    # usage stats per student (UsageEvent, org_id 기준)
    usage_rows = db.execute(
        select(
            UsageEvent.student_id,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.total_cost_usd), 0),
            func.max(UsageEvent.occurred_at),
        )
        .where(
            UsageEvent.partner_id == org_id,
            UsageEvent.student_id.in_(student_ids),
            UsageEvent.request_type == "llm_chat",
        )
        .group_by(UsageEvent.student_id)
    ).all()

    usage_map: dict[int, tuple] = {}
    for row in usage_rows:
        usage_map[row[0]] = (row[1], row[2], row[3])  # (count, cost, last_at)

    # 3) 조합
    results: list[StudentDetailResponse] = []
    for st in students:
        sid = st.id
        usage = usage_map.get(sid, (0, 0, None))

        results.append(
            StudentDetailResponse(
                id=sid,
                partner_id=st.partner_id,
                full_name=st.full_name,
                email=st.email,
                status=st.status,
                joined_at=st.joined_at,
                primary_contact=st.primary_contact,
                user_id=st.user_id,
                enrollments=enrollment_map.get(sid, []),
                conversation_count=usage[0],
                total_cost=_d(usage[1]),
                last_activity_at=usage[2],
            )
        )

    return results
