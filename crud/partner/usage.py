# crud/partner/usage.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session

from models.partner.usage import UsageEvent, UsageDaily, UsageModelMonthly


# =========================
# helpers
# =========================
def _d(v: Any) -> Decimal:
    return Decimal(str(v or 0))


def _apply_usage_events_filters(
    stmt,
    *,
    partner_id: int,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    success: Optional[bool] = None,
):
    stmt = stmt.where(UsageEvent.partner_id == partner_id)

    if start_at is not None:
        stmt = stmt.where(UsageEvent.occurred_at >= start_at)
    if end_at is not None:
        # end_at은 "미만"으로 두는 게 pagination/범위 계산에서 덜 헷갈림
        stmt = stmt.where(UsageEvent.occurred_at < end_at)

    if request_type is not None:
        stmt = stmt.where(UsageEvent.request_type == request_type)
    if provider is not None:
        stmt = stmt.where(UsageEvent.provider == provider)
    if model_name is not None:
        stmt = stmt.where(UsageEvent.model_name == model_name)

    if class_id is not None:
        stmt = stmt.where(UsageEvent.class_id == class_id)
    if enrollment_id is not None:
        stmt = stmt.where(UsageEvent.enrollment_id == enrollment_id)
    if student_id is not None:
        stmt = stmt.where(UsageEvent.student_id == student_id)

    if success is not None:
        stmt = stmt.where(UsageEvent.success == success)

    return stmt


def _apply_usage_daily_filters(
    stmt,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dim_type: Optional[str] = None,
    dim_id: Optional[int] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
):
    stmt = stmt.where(UsageDaily.partner_id == partner_id)

    if start_date is not None:
        stmt = stmt.where(UsageDaily.usage_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(UsageDaily.usage_date <= end_date)

    if dim_type is not None:
        stmt = stmt.where(UsageDaily.dim_type == dim_type)
    if dim_id is not None:
        stmt = stmt.where(UsageDaily.dim_id == dim_id)

    if request_type is not None:
        stmt = stmt.where(UsageDaily.request_type == request_type)
    if provider is not None:
        stmt = stmt.where(UsageDaily.provider == provider)
    if model_name is not None:
        stmt = stmt.where(UsageDaily.model_name == model_name)

    return stmt


# =========================
# UsageEvent (raw logs) - read only
# =========================
def count_usage_events(
    db: Session,
    *,
    partner_id: int,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    success: Optional[bool] = None,
) -> int:
    stmt = select(func.count(UsageEvent.id))
    stmt = _apply_usage_events_filters(
        stmt,
        partner_id=partner_id,
        start_at=start_at,
        end_at=end_at,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
        class_id=class_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        success=success,
    )
    return int(db.execute(stmt).scalar() or 0)


def list_usage_events(
    db: Session,
    *,
    partner_id: int,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    success: Optional[bool] = None,
    offset: int = 0,
    limit: int = 50,
    newest_first: bool = True,
) -> List[UsageEvent]:
    stmt = select(UsageEvent)
    stmt = _apply_usage_events_filters(
        stmt,
        partner_id=partner_id,
        start_at=start_at,
        end_at=end_at,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
        class_id=class_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        success=success,
    )

    if newest_first:
        stmt = stmt.order_by(desc(UsageEvent.occurred_at), desc(UsageEvent.id))
    else:
        stmt = stmt.order_by(UsageEvent.occurred_at.asc(), UsageEvent.id.asc())

    stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


# =========================
# UsageDaily (daily aggregates) - read only
# =========================
def list_usage_daily_rows(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dim_type: Optional[str] = None,
    dim_id: Optional[int] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> List[UsageDaily]:
    stmt = select(UsageDaily)
    stmt = _apply_usage_daily_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        dim_type=dim_type,
        dim_id=dim_id,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )
    stmt = stmt.order_by(UsageDaily.usage_date.asc())
    return list(db.execute(stmt).scalars().all())


# =========================
# instructor-analytics: KPI / Timeseries / Breakdowns
# =========================
def get_usage_kpi(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    주의:
    - KPI 합계는 dim_type='partner'만 써야 중복 집계가 안 생김.
    - avg_latency_ms는 일단 request_count 가중 평균으로 근사.
    - p95_latency_ms는 기간 전체 p95를 정확히 합칠 수 없어서 "최대값" 근사.
      정확한 p95가 필요하면 usage_events에서 percentile_cont로 뽑아야 함.
    """
    base_stmt = select(
        func.coalesce(func.sum(UsageDaily.total_cost_usd), 0).label("total_cost_usd"),
        func.coalesce(func.sum(UsageDaily.request_count), 0).label("request_count"),
        func.coalesce(func.sum(UsageDaily.turn_count), 0).label("turn_count"),
        func.coalesce(func.sum(UsageDaily.session_count), 0).label("session_count"),
        func.coalesce(func.sum(UsageDaily.message_count), 0).label("message_count"),
        func.coalesce(func.sum(UsageDaily.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(UsageDaily.success_count), 0).label("success_count"),
        func.coalesce(func.sum(UsageDaily.error_count), 0).label("error_count"),
        # weighted avg latency (근사): sum(avg_latency * request_count) / sum(request_count)
        (
            func.nullif(func.sum(UsageDaily.request_count), 0)
        ).label("_den"),
        func.coalesce(
            func.sum(UsageDaily.request_count * UsageDaily.avg_latency_ms), 0
        ).label("_lat_num"),
        func.max(UsageDaily.p95_latency_ms).label("p95_latency_ms_approx"),
    ).where(UsageDaily.dim_type == "partner")

    base_stmt = _apply_usage_daily_filters(
        base_stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        dim_type="partner",
        dim_id=None,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    row = db.execute(base_stmt).mappings().one()

    den = row["_den"]
    lat_num = row["_lat_num"]
    avg_latency_ms = None
    if den:
        # Decimal로 유지
        avg_latency_ms = _d(lat_num) / _d(den)

    # active students/classes: dim_type별 distinct dim_id
    students_stmt = select(func.count(func.distinct(UsageDaily.dim_id))).where(UsageDaily.dim_type == "student")
    students_stmt = _apply_usage_daily_filters(
        students_stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        dim_type="student",
        dim_id=None,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )
    active_students = int(db.execute(students_stmt).scalar() or 0)

    classes_stmt = select(func.count(func.distinct(UsageDaily.dim_id))).where(UsageDaily.dim_type == "class")
    classes_stmt = _apply_usage_daily_filters(
        classes_stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        dim_type="class",
        dim_id=None,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )
    active_classes = int(db.execute(classes_stmt).scalar() or 0)

    return {
        "total_cost_usd": _d(row["total_cost_usd"]),
        "request_count": int(row["request_count"] or 0),
        "turn_count": int(row["turn_count"] or 0),
        "session_count": int(row["session_count"] or 0),
        "message_count": int(row["message_count"] or 0),
        "total_tokens": int(row["total_tokens"] or 0),
        "success_count": int(row["success_count"] or 0),
        "error_count": int(row["error_count"] or 0),
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": row["p95_latency_ms_approx"],  # 근사
        "active_students": active_students,
        "active_classes": active_classes,
    }


def get_usage_timeseries_daily(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    stmt = select(
        UsageDaily.usage_date.label("usage_date"),
        func.coalesce(func.sum(UsageDaily.total_cost_usd), 0).label("total_cost_usd"),
        func.coalesce(func.sum(UsageDaily.request_count), 0).label("request_count"),
        func.coalesce(func.sum(UsageDaily.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(UsageDaily.error_count), 0).label("error_count"),
    ).where(UsageDaily.dim_type == "partner")

    stmt = _apply_usage_daily_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        dim_type="partner",
        dim_id=None,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    stmt = stmt.group_by(UsageDaily.usage_date).order_by(UsageDaily.usage_date.asc())
    rows = db.execute(stmt).mappings().all()

    return [
        {
            "usage_date": r["usage_date"],
            "total_cost_usd": _d(r["total_cost_usd"]),
            "request_count": int(r["request_count"] or 0),
            "total_tokens": int(r["total_tokens"] or 0),
            "error_count": int(r["error_count"] or 0),
        }
        for r in rows
    ]


def get_usage_model_breakdown(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """
    모델별 집계(점유율/랭킹).
    dim_type='partner'만 사용해서 중복 방지.
    """
    stmt = select(
        UsageDaily.provider.label("provider"),
        UsageDaily.model_name.label("model_name"),
        func.coalesce(func.sum(UsageDaily.total_cost_usd), 0).label("total_cost_usd"),
        func.coalesce(func.sum(UsageDaily.request_count), 0).label("request_count"),
        func.coalesce(func.sum(UsageDaily.total_tokens), 0).label("total_tokens"),
    ).where(UsageDaily.dim_type == "partner")

    stmt = _apply_usage_daily_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        dim_type="partner",
        dim_id=None,
        request_type=request_type,
        provider=None,
        model_name=None,
    )

    stmt = (
        stmt.group_by(UsageDaily.provider, UsageDaily.model_name)
        .order_by(desc(func.sum(UsageDaily.total_cost_usd)))
        .limit(top_n)
    )
    rows = db.execute(stmt).mappings().all()

    total_cost_all = sum((_d(r["total_cost_usd"]) for r in rows), Decimal("0"))

    out: List[Dict[str, Any]] = []
    for r in rows:
        cost = _d(r["total_cost_usd"])
        share = None
        if total_cost_all > 0:
            share = (cost / total_cost_all) * Decimal("100")
        out.append(
            {
                "provider": r["provider"],
                "model_name": r["model_name"],
                "total_cost_usd": cost,
                "request_count": int(r["request_count"] or 0),
                "total_tokens": int(r["total_tokens"] or 0),
                "share_pct": share,
            }
        )
    return out


def get_usage_dim_breakdown(
    db: Session,
    *,
    partner_id: int,
    dim_type: str,  # "class" | "student" | "enrollment"
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """
    클래스/학생/수강(enrollment)별 랭킹.
    usage_daily는 provider/model별로 row가 쪼개져 있으니까 dim_id로 다시 합쳐서 내려줌.
    """
    if dim_type not in ("class", "student", "enrollment"):
        raise ValueError("dim_type must be one of: class, student, enrollment")

    stmt = select(
        UsageDaily.dim_id.label("dim_id"),
        func.coalesce(func.sum(UsageDaily.total_cost_usd), 0).label("total_cost_usd"),
        func.coalesce(func.sum(UsageDaily.request_count), 0).label("request_count"),
        func.coalesce(func.sum(UsageDaily.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(UsageDaily.error_count), 0).label("error_count"),
    ).where(UsageDaily.dim_type == dim_type)

    stmt = _apply_usage_daily_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        dim_type=dim_type,
        dim_id=None,
        request_type=request_type,
        provider=None,
        model_name=None,
    )

    stmt = (
        stmt.group_by(UsageDaily.dim_id)
        .order_by(desc(func.sum(UsageDaily.total_cost_usd)))
        .limit(top_n)
    )
    rows = db.execute(stmt).mappings().all()

    return [
        {
            "dim_type": dim_type,
            "dim_id": int(r["dim_id"]),
            "total_cost_usd": _d(r["total_cost_usd"]),
            "request_count": int(r["request_count"] or 0),
            "total_tokens": int(r["total_tokens"] or 0),
            "error_count": int(r["error_count"] or 0),
            # dim_label은 여기서 조인하지 말고 service에서 class/student 테이블 붙여서 채우는 걸 추천
            "dim_label": None,
        }
        for r in rows
    ]


# =========================
# optional: monthly model aggregates
# =========================
def list_usage_model_monthly(
    db: Session,
    *,
    partner_id: int,
    start_month: Optional[date] = None,  # YYYY-MM-01
    end_month: Optional[date] = None,    # YYYY-MM-01
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> List[UsageModelMonthly]:
    stmt = select(UsageModelMonthly).where(UsageModelMonthly.partner_id == partner_id)

    if start_month is not None:
        stmt = stmt.where(UsageModelMonthly.month >= start_month)
    if end_month is not None:
        stmt = stmt.where(UsageModelMonthly.month <= end_month)

    if request_type is not None:
        stmt = stmt.where(UsageModelMonthly.request_type == request_type)
    if provider is not None:
        stmt = stmt.where(UsageModelMonthly.provider == provider)
    if model_name is not None:
        stmt = stmt.where(UsageModelMonthly.model_name == model_name)

    stmt = stmt.order_by(UsageModelMonthly.month.asc())
    return list(db.execute(stmt).scalars().all())
