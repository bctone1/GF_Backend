# crud/partner/usage.py
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from zoneinfo import ZoneInfo

from sqlalchemy import select, func, desc, cast, Date, case
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.partner.usage import UsageEvent, UsageDaily, UsageModelMonthly

KST = ZoneInfo("Asia/Seoul")


# =========================
# helpers
# =========================
def _d(v: Any) -> Decimal:
    return Decimal(str(v or 0))


def _date_range_to_utc(start_date: Optional[date], end_date: Optional[date]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    usage_date(로컬 KST 기준)로 받은 범위를 occurred_at(timestamptz) 필터로 쓰기 위해 UTC datetime 범위로 변환.
    - start_date: inclusive (00:00 KST)
    - end_date: inclusive -> end_at exclusive (end_date + 1일 00:00 KST)
    """
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    if start_date is not None:
        start_kst = datetime.combine(start_date, time.min).replace(tzinfo=KST)
        start_at = start_kst.astimezone(timezone.utc)

    if end_date is not None:
        end_kst_excl = datetime.combine(end_date + timedelta(days=1), time.min).replace(tzinfo=KST)
        end_at = end_kst_excl.astimezone(timezone.utc)

    return start_at, end_at


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
    session_id: Optional[int] = None,
    success: Optional[bool] = None,
):
    stmt = stmt.where(UsageEvent.partner_id == partner_id)

    if start_at is not None:
        stmt = stmt.where(UsageEvent.occurred_at >= start_at)
    if end_at is not None:
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
    if session_id is not None:
        stmt = stmt.where(UsageEvent.session_id == session_id)

    if success is not None:
        stmt = stmt.where(UsageEvent.success == success)

    return stmt


def _kst_date_expr():
    # Postgres: timezone('Asia/Seoul', occurred_at)::date
    return cast(func.timezone("Asia/Seoul", UsageEvent.occurred_at), Date)


# =========================
# UsageEvent - write (idempotent)
# =========================
def upsert_usage_event_idempotent(
    db: Session,
    *,
    request_id: str,
    partner_id: int,
    request_type: str,
    provider: str,
    model_name: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    session_id: Optional[int] = None,
    total_tokens: int = 0,
    media_duration_seconds: int = 0,
    latency_ms: Optional[int] = None,
    total_cost_usd: Decimal = Decimal("0"),
    success: bool = True,
    error_code: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> UsageEvent:
    """
    request_id UNIQUE 기준 멱등 insert.
    - 이미 있으면 기존 row 반환
    """
    values: Dict[str, Any] = {
        "request_id": request_id,
        "partner_id": partner_id,
        "request_type": request_type,
        "provider": provider,
        "model_name": model_name,
        "occurred_at": occurred_at,
        "class_id": class_id,
        "enrollment_id": enrollment_id,
        "student_id": student_id,
        "session_id": session_id,
        "total_tokens": int(total_tokens or 0),
        "media_duration_seconds": int(media_duration_seconds or 0),
        "latency_ms": latency_ms,
        "total_cost_usd": _d(total_cost_usd),
        "success": bool(success),
        "error_code": error_code,
        "meta": meta or {},
    }
    # occurred_at=None이면 server_default(now()) 쓰도록 제거
    if values["occurred_at"] is None:
        values.pop("occurred_at")

    ins = (
        pg_insert(UsageEvent)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["request_id"])
        .returning(UsageEvent.id)
    )
    inserted_id = db.execute(ins).scalar()

    if inserted_id is not None:
        row = db.get(UsageEvent, int(inserted_id))
        assert row is not None
        return row

    # conflict: 기존 row 반환
    stmt = select(UsageEvent).where(UsageEvent.request_id == request_id)
    row = db.execute(stmt).scalars().one()
    return row


# =========================
# UsageEvent - read
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
    session_id: Optional[int] = None,
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
        session_id=session_id,
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
    session_id: Optional[int] = None,
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
        session_id=session_id,
        success=success,
    )

    if newest_first:
        stmt = stmt.order_by(desc(UsageEvent.occurred_at), desc(UsageEvent.id))
    else:
        stmt = stmt.order_by(UsageEvent.occurred_at.asc(), UsageEvent.id.asc())

    stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


# =========================
# instructor-analytics (on-read, UsageEvent 기반)
# =========================
def get_usage_kpi_on_read(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    start_at, end_at = _date_range_to_utc(start_date, end_date)

    stmt = select(
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.count(func.distinct(UsageEvent.session_id)).label("session_count"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(True), 1), else_=0)), 0).label("success_count"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
        func.avg(UsageEvent.latency_ms).label("avg_latency_ms"),
        func.count(func.distinct(UsageEvent.student_id)).label("active_students"),
        func.count(func.distinct(UsageEvent.class_id)).label("active_classes"),
    )

    stmt = _apply_usage_events_filters(
        stmt,
        partner_id=partner_id,
        start_at=start_at,
        end_at=end_at,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    row = db.execute(stmt).mappings().one()

    avg_latency = row["avg_latency_ms"]
    avg_latency_ms = _d(avg_latency) if avg_latency is not None else None

    return {
        "total_cost_usd": _d(row["total_cost_usd"]),
        "request_count": int(row["request_count"] or 0),
        "session_count": int(row["session_count"] or 0),
        "total_tokens": int(row["total_tokens"] or 0),
        "success_count": int(row["success_count"] or 0),
        "error_count": int(row["error_count"] or 0),
        "avg_latency_ms": avg_latency_ms,
        "active_students": int(row["active_students"] or 0),
        "active_classes": int(row["active_classes"] or 0),
    }


def get_usage_timeseries_daily_on_read(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    start_at, end_at = _date_range_to_utc(start_date, end_date)
    kst_date = _kst_date_expr()

    stmt = select(
        kst_date.label("usage_date"),
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
    )

    stmt = _apply_usage_events_filters(
        stmt,
        partner_id=partner_id,
        start_at=start_at,
        end_at=end_at,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    stmt = stmt.group_by(kst_date).order_by(kst_date.asc())
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


def get_usage_model_breakdown_on_read(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    start_at, end_at = _date_range_to_utc(start_date, end_date)

    stmt = select(
        UsageEvent.provider.label("provider"),
        UsageEvent.model_name.label("model_name"),
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
    )

    stmt = _apply_usage_events_filters(
        stmt,
        partner_id=partner_id,
        start_at=start_at,
        end_at=end_at,
        request_type=request_type,
        provider=None,
        model_name=None,
    )

    stmt = (
        stmt.group_by(UsageEvent.provider, UsageEvent.model_name)
        .order_by(desc(func.sum(UsageEvent.total_cost_usd)))
        .limit(top_n)
    )
    rows = db.execute(stmt).mappings().all()

    total_cost_all = sum((_d(r["total_cost_usd"]) for r in rows), Decimal("0"))

    out: List[Dict[str, Any]] = []
    for r in rows:
        cost = _d(r["total_cost_usd"])
        share = (cost / total_cost_all) * Decimal("100") if total_cost_all > 0 else None
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


def get_usage_dim_breakdown_on_read(
    db: Session,
    *,
    partner_id: int,
    dim_type: str,  # "class" | "student" | "enrollment"
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    if dim_type not in ("class", "student", "enrollment"):
        raise ValueError("dim_type must be one of: class, student, enrollment")

    start_at, end_at = _date_range_to_utc(start_date, end_date)

    col = {
        "class": UsageEvent.class_id,
        "student": UsageEvent.student_id,
        "enrollment": UsageEvent.enrollment_id,
    }[dim_type]

    stmt = select(
        col.label("dim_id"),
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
    ).where(col.is_not(None))

    stmt = _apply_usage_events_filters(
        stmt,
        partner_id=partner_id,
        start_at=start_at,
        end_at=end_at,
        request_type=request_type,
        provider=None,
        model_name=None,
    )

    stmt = (
        stmt.group_by(col)
        .order_by(desc(func.sum(UsageEvent.total_cost_usd)))
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
            "dim_label": None,  # service에서 조인해서 채우는 걸 추천
        }
        for r in rows
    ]


# =========================
# optional: daily/monthly (나중 ETL용)
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
    stmt = select(UsageDaily).where(UsageDaily.partner_id == partner_id)

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

    stmt = stmt.order_by(UsageDaily.usage_date.asc())
    return list(db.execute(stmt).scalars().all())


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
