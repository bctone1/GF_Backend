# service/partner/class_summary.py
"""강의 목록 + 통계 요약 서비스."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from models.partner.partner_core import Partner
from models.partner.course import Class, InviteCode
from models.partner.student import Enrollment
from models.partner.usage import UsageEvent, UsageDaily

from schemas.partner.classes import ClassSummaryResponse


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def _seoul_date_expr(ts_col):
    return func.date(func.timezone("Asia/Seoul", ts_col))


def _db_seoul_today(db: Session) -> date:
    return db.execute(
        select(func.date(func.timezone("Asia/Seoul", func.now())))
    ).scalar_one()


def _budget_status(usage_pct: Decimal) -> Literal["ok", "warning", "alert"]:
    if usage_pct >= 80:
        return "alert"
    if usage_pct >= 50:
        return "warning"
    return "ok"


def list_classes_with_stats(
    db: Session,
    *,
    partner: Partner,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ClassSummaryResponse]:
    """강의 목록을 통계와 함께 반환한다."""
    today = _db_seoul_today(db)
    org_id = partner.org_id

    # 1) Class 목록 조회
    conds = [Class.partner_id == partner.id]
    if status_filter:
        conds.append(Class.status == status_filter)

    classes = (
        db.execute(
            select(Class)
            .where(and_(*conds))
            .order_by(Class.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    if not classes:
        return []

    class_ids = [c.id for c in classes]

    # 2) 일괄 통계 쿼리 (N+1 방지)

    # student_count per class
    student_counts = dict(
        db.execute(
            select(
                Enrollment.class_id,
                func.count(func.distinct(Enrollment.student_id)),
            )
            .where(
                Enrollment.class_id.in_(class_ids),
                Enrollment.status == "active",
            )
            .group_by(Enrollment.class_id)
        ).all()
    )

    # conversation_count + total_cost per class (UsageEvent, org_id 기준)
    conv_stats = dict(
        db.execute(
            select(
                UsageEvent.class_id,
                func.count(UsageEvent.id),
                func.coalesce(func.sum(UsageEvent.total_cost_usd), 0),
            )
            .where(
                UsageEvent.partner_id == org_id,
                UsageEvent.class_id.in_(class_ids),
                UsageEvent.request_type == "llm_chat",
            )
            .group_by(UsageEvent.class_id)
        ).all()
    )  # {class_id: (count, cost)}

    # budget_used per class: UsageDaily(dim_type='class') + 오늘 UsageEvent
    daily_costs = dict(
        db.execute(
            select(
                UsageDaily.dim_id,
                func.coalesce(func.sum(UsageDaily.total_cost_usd), 0),
            )
            .where(
                UsageDaily.partner_id == org_id,
                UsageDaily.dim_type == "class",
                UsageDaily.dim_id.in_(class_ids),
            )
            .group_by(UsageDaily.dim_id)
        ).all()
    )

    today_costs = dict(
        db.execute(
            select(
                UsageEvent.class_id,
                func.coalesce(func.sum(UsageEvent.total_cost_usd), 0),
            )
            .where(
                UsageEvent.partner_id == org_id,
                UsageEvent.class_id.in_(class_ids),
                _seoul_date_expr(UsageEvent.occurred_at) == today,
            )
            .group_by(UsageEvent.class_id)
        ).all()
    )

    # invite_code per class (첫 active 코드)
    invite_codes = dict(
        db.execute(
            select(
                InviteCode.class_id,
                func.min(InviteCode.code),
            )
            .where(
                InviteCode.class_id.in_(class_ids),
                InviteCode.status == "active",
            )
            .group_by(InviteCode.class_id)
        ).all()
    )

    # 3) 조합
    results: list[ClassSummaryResponse] = []
    for cls in classes:
        cid = cls.id
        conv_row = conv_stats.get(cid, (0, 0))
        conversation_count = conv_row[0]
        total_cost = _d(conv_row[1])

        budget_used = _d(daily_costs.get(cid, 0)) + _d(today_costs.get(cid, 0))
        bl = cls.budget_limit

        if bl is not None and _d(bl) > 0:
            budget_pct = (budget_used / _d(bl)) * Decimal("100")
        else:
            budget_pct = Decimal("0")

        # days_remaining
        days_remaining = None
        if cls.end_at is not None:
            end_date = cls.end_at.date() if hasattr(cls.end_at, "date") else cls.end_at
            days_remaining = (end_date - today).days

        results.append(
            ClassSummaryResponse(
                id=cid,
                name=cls.name,
                status=cls.status,
                description=cls.description,
                start_at=cls.start_at,
                end_at=cls.end_at,
                capacity=cls.capacity,
                budget_limit=bl,
                student_count=student_counts.get(cid, 0),
                conversation_count=conversation_count,
                total_cost=total_cost,
                days_remaining=days_remaining,
                budget_used=budget_used,
                budget_percent=budget_pct,
                budget_status=_budget_status(budget_pct) if bl is not None else "ok",
                invite_code=invite_codes.get(cid),
                created_at=cls.created_at,
            )
        )

    return results
