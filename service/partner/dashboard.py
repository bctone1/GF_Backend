# service/partner/dashboard.py
"""파트너 대시보드 통합 응답 서비스."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Literal

from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import Session

from models.partner.partner_core import Partner, Org
from models.partner.course import Class
from models.partner.student import Student, Enrollment
from models.partner.usage import UsageEvent, UsageDaily
from models.partner.activity import ActivityEvent

import crud.partner.activity as activity_crud

from schemas.partner.dashboard import (
    DashboardResponse,
    DashboardWelcome,
    DashboardStatCards,
    DashboardActivityEvent,
    DashboardTopStudent,
    DashboardClassBudget,
)


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def _db_seoul_today(db: Session) -> date:
    """DB 서버 시간 기준 Asia/Seoul 오늘."""
    return db.execute(
        select(func.date(func.timezone("Asia/Seoul", func.now())))
    ).scalar_one()


def _seoul_date_expr(ts_col):
    return func.date(func.timezone("Asia/Seoul", ts_col))


# ------------------------------------------------------------------
# 1) Welcome
# ------------------------------------------------------------------
def _build_welcome(db: Session, partner: Partner) -> DashboardWelcome:
    org = db.get(Org, partner.org_id)
    return DashboardWelcome(
        partner_id=partner.id,
        partner_name=partner.full_name,
        org_name=org.name if org else "",
    )


# ------------------------------------------------------------------
# 2) Stat Cards
# ------------------------------------------------------------------
def _build_stat_cards(
    db: Session,
    *,
    partner: Partner,
    today: date,
) -> DashboardStatCards:
    org_id = partner.org_id

    # active_classes: Class 기준 (partner.id = 강사 id)
    active_classes = db.execute(
        select(func.count(Class.id)).where(
            Class.partner_id == partner.id,
            Class.status == "active",
        )
    ).scalar_one()

    # active_students: 강사의 active class에 active enrollment된 학생 수
    active_students = db.execute(
        select(func.count(func.distinct(Enrollment.student_id))).where(
            Enrollment.class_id.in_(
                select(Class.id).where(
                    Class.partner_id == partner.id,
                    Class.status == "active",
                )
            ),
            Enrollment.status == "active",
        )
    ).scalar_one()

    # today_conversations: UsageEvent (org_id 기준) + 오늘 + llm_chat
    today_conversations = db.execute(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.partner_id == org_id,
            _seoul_date_expr(UsageEvent.occurred_at) == today,
            UsageEvent.request_type == "llm_chat",
        )
    ).scalar_one()

    # weekly_cost: UsageDaily 최근 7일 (dim_type='partner') + 오늘 UsageEvent
    week_ago = today - timedelta(days=6)

    daily_cost = db.execute(
        select(func.coalesce(func.sum(UsageDaily.total_cost_usd), 0)).where(
            UsageDaily.partner_id == org_id,
            UsageDaily.dim_type == "partner",
            UsageDaily.usage_date >= week_ago,
            UsageDaily.usage_date < today,
        )
    ).scalar_one()

    today_cost = db.execute(
        select(func.coalesce(func.sum(UsageEvent.total_cost_usd), 0)).where(
            UsageEvent.partner_id == org_id,
            _seoul_date_expr(UsageEvent.occurred_at) == today,
        )
    ).scalar_one()

    return DashboardStatCards(
        active_classes=int(active_classes or 0),
        active_students=int(active_students or 0),
        today_conversations=int(today_conversations or 0),
        weekly_cost=_d(daily_cost) + _d(today_cost),
    )


# ------------------------------------------------------------------
# 3) Recent Activity
# ------------------------------------------------------------------
def _build_recent_activity(
    db: Session,
    *,
    org_id: int,
    limit: int,
) -> List[DashboardActivityEvent]:
    events = activity_crud.list_activity_events(
        db, partner_id=org_id, limit=limit,
    )
    return [DashboardActivityEvent.model_validate(e) for e in events]


# ------------------------------------------------------------------
# 4) Top Students
# ------------------------------------------------------------------
def _build_top_students(
    db: Session,
    *,
    org_id: int,
    today: date,
    limit: int,
) -> List[DashboardTopStudent]:
    # 최근 30일 대화 수 기준 상위 학생
    since = today - timedelta(days=30)

    stmt = (
        select(
            UsageEvent.student_id,
            func.count(UsageEvent.id).label("conv_count"),
        )
        .where(
            UsageEvent.partner_id == org_id,
            UsageEvent.request_type == "llm_chat",
            UsageEvent.student_id.is_not(None),
            _seoul_date_expr(UsageEvent.occurred_at) >= since,
        )
        .group_by(UsageEvent.student_id)
        .order_by(func.count(UsageEvent.id).desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return []

    # student_id → full_name 조회
    student_ids = [r[0] for r in rows]
    name_map = {}
    if student_ids:
        students = db.execute(
            select(Student.id, Student.full_name).where(Student.id.in_(student_ids))
        ).all()
        name_map = {s[0]: s[1] for s in students}

    return [
        DashboardTopStudent(
            rank=idx + 1,
            student_id=row[0],
            student_name=name_map.get(row[0], f"Student #{row[0]}"),
            conversation_count=row[1],
        )
        for idx, row in enumerate(rows)
    ]


# ------------------------------------------------------------------
# 5) Class Budgets
# ------------------------------------------------------------------
def _budget_status(usage_pct: Decimal) -> Literal["ok", "warning", "alert"]:
    if usage_pct >= 80:
        return "alert"
    if usage_pct >= 50:
        return "warning"
    return "ok"


def _build_class_budgets(
    db: Session,
    *,
    partner: Partner,
    today: date,
) -> List[DashboardClassBudget]:
    org_id = partner.org_id

    # 강사의 active class 목록
    classes = db.execute(
        select(Class).where(
            Class.partner_id == partner.id,
            Class.status == "active",
        )
    ).scalars().all()

    if not classes:
        return []

    class_ids = [c.id for c in classes]

    # 각 class별 총 사용량 (UsageDaily dim_type='class' + 오늘 UsageEvent)
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

    results: List[DashboardClassBudget] = []
    for cls in classes:
        total_used = _d(daily_costs.get(cls.id, 0)) + _d(today_costs.get(cls.id, 0))
        bl = cls.budget_limit

        if bl is not None and _d(bl) > 0:
            pct = (total_used / _d(bl)) * Decimal("100")
        else:
            pct = Decimal("0")

        results.append(
            DashboardClassBudget(
                class_id=cls.id,
                class_name=cls.name,
                budget_used=total_used,
                budget_limit=bl,
                usage_percent=pct,
                status=_budget_status(pct) if bl is not None else "ok",
            )
        )

    return results


# ------------------------------------------------------------------
# 6) Lazy Budget Alert
# ------------------------------------------------------------------
def _maybe_emit_budget_alerts(
    db: Session,
    *,
    org_id: int,
    class_budgets: List[DashboardClassBudget],
    today: date,
) -> None:
    """80% 초과 class가 오늘 아직 alert 미발생이면 자동 생성."""
    alert_classes = [b for b in class_budgets if b.status == "alert"]
    if not alert_classes:
        return

    alert_class_ids = [b.class_id for b in alert_classes]

    # 오늘 이미 발생한 budget_alert 확인
    existing = db.execute(
        select(ActivityEvent.class_id).where(
            ActivityEvent.partner_id == org_id,
            ActivityEvent.event_type == "budget_alert",
            ActivityEvent.class_id.in_(alert_class_ids),
            _seoul_date_expr(ActivityEvent.created_at) == today,
        )
    ).scalars().all()
    already_alerted = set(existing)

    for b in alert_classes:
        if b.class_id in already_alerted:
            continue
        activity_crud.create_activity_event(
            db,
            partner_id=org_id,
            event_type="budget_alert",
            title=f"예산 경고: {b.class_name}",
            description=f"사용률 {b.usage_percent:.0f}% (한도 ${b.budget_limit})",
            class_id=b.class_id,
            meta={"usage_percent": float(b.usage_percent)},
        )

    db.commit()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def get_partner_dashboard(
    db: Session,
    *,
    partner: Partner,
    activity_limit: int = 10,
    top_students_limit: int = 5,
) -> DashboardResponse:
    """파트너 대시보드 통합 응답을 생성한다."""
    today = _db_seoul_today(db)
    org_id = partner.org_id

    welcome = _build_welcome(db, partner)
    stat_cards = _build_stat_cards(db, partner=partner, today=today)
    class_budgets = _build_class_budgets(db, partner=partner, today=today)

    # lazy budget alert 생성 (class_budgets 계산 후)
    _maybe_emit_budget_alerts(
        db, org_id=org_id, class_budgets=class_budgets, today=today,
    )

    recent_activity = _build_recent_activity(
        db, org_id=org_id, limit=activity_limit,
    )
    top_students = _build_top_students(
        db, org_id=org_id, today=today, limit=top_students_limit,
    )

    return DashboardResponse(
        welcome=welcome,
        stat_cards=stat_cards,
        recent_activity=recent_activity,
        top_students=top_students,
        class_budgets=class_budgets,
    )
