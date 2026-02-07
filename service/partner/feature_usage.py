# service/partner/feature_usage.py
from __future__ import annotations

from datetime import date
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.partner.partner_core import Partner
from models.partner.student import Student
from models.partner.usage import UsageEvent
from models.user.document import Document
from models.user.project import UserProject

from schemas.partner.usage import FeatureUsageResponse, FeatureUsageItem


def _seoul_date_expr(ts_col):
    """Helper: convert a timestamptz column to Seoul date."""
    return func.date(func.timezone("Asia/Seoul", ts_col))


def get_feature_usage(
    db: Session,
    *,
    partner: Partner,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> FeatureUsageResponse:
    """기능 활용 현황: 비교모드, 지식베이스(RAG), 에이전트, 프로젝트."""

    # ── total active students under this partner ──
    total_students: int = db.execute(
        select(func.count(Student.id))
        .where(Student.partner_id == partner.id, Student.status == "active")
    ).scalar_one()

    # ── student → user_id mapping (for cross-schema queries) ──
    student_rows = db.execute(
        select(Student.id, Student.user_id)
        .where(
            Student.partner_id == partner.id,
            Student.user_id.isnot(None),
        )
    ).all()
    user_ids: List[int] = [r[1] for r in student_rows]

    # ── compare mode (from UsageEvent.meta->>'mode' == 'compare') ──
    compare_filters = [
        UsageEvent.partner_id == partner.org_id,
        UsageEvent.request_type == "llm_chat",
        UsageEvent.meta["mode"].as_string() == "compare",
    ]
    if start_date:
        compare_filters.append(_seoul_date_expr(UsageEvent.occurred_at) >= start_date)
    if end_date:
        compare_filters.append(_seoul_date_expr(UsageEvent.occurred_at) <= end_date)

    compare_row = db.execute(
        select(
            func.count(func.distinct(UsageEvent.student_id)),
            func.count(UsageEvent.id),
        ).where(*compare_filters)
    ).one()

    compare_mode = FeatureUsageItem(
        student_count=compare_row[0] or 0,
        total_students=total_students,
        usage_count=compare_row[1] or 0,
    )

    # ── knowledge_base (documents uploaded by partner's students) ──
    if user_ids:
        kb_filters = [Document.owner_id.in_(user_ids)]
        if start_date:
            kb_filters.append(_seoul_date_expr(Document.uploaded_at) >= start_date)
        if end_date:
            kb_filters.append(_seoul_date_expr(Document.uploaded_at) <= end_date)

        kb_row = db.execute(
            select(
                func.count(func.distinct(Document.owner_id)),
                func.count(Document.knowledge_id),
            ).where(*kb_filters)
        ).one()
        knowledge_base = FeatureUsageItem(
            student_count=kb_row[0] or 0,
            total_students=total_students,
            usage_count=kb_row[1] or 0,
        )
    else:
        knowledge_base = FeatureUsageItem(total_students=total_students)

    # ── project (projects created by partner's students) ──
    if user_ids:
        proj_filters = [UserProject.owner_id.in_(user_ids)]
        if start_date:
            proj_filters.append(_seoul_date_expr(UserProject.created_at) >= start_date)
        if end_date:
            proj_filters.append(_seoul_date_expr(UserProject.created_at) <= end_date)

        proj_row = db.execute(
            select(
                func.count(func.distinct(UserProject.owner_id)),
                func.count(UserProject.project_id),
            ).where(*proj_filters)
        ).one()
        project = FeatureUsageItem(
            student_count=proj_row[0] or 0,
            total_students=total_students,
            usage_count=proj_row[1] or 0,
        )
    else:
        project = FeatureUsageItem(total_students=total_students)

    # ── agent (placeholder — feature not yet implemented) ──
    agent = FeatureUsageItem(
        student_count=0,
        total_students=total_students,
        usage_count=0,
    )

    return FeatureUsageResponse(
        compare_mode=compare_mode,
        knowledge_base=knowledge_base,
        agent=agent,
        project=project,
    )
