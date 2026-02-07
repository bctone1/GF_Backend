# service/partner/instructor_analytics.py
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Iterable, Tuple

from sqlalchemy import select, func, desc, case, literal
from sqlalchemy.orm import Session

import crud.partner.usage as usage_crud
from models.partner.usage import UsageDaily, UsageEvent

from schemas.partner.usage import (
    InstructorUsageAnalyticsResponse,
    UsageKpiResponse,
    UsageTimeSeriesPoint,
    UsageModelBreakdownItem,
    UsageDimBreakdownItem,
)

# =========================
# optional label resolvers
# =========================
try:
    from models.partner.course import Class  # type: ignore
except Exception:
    Class = None  # type: ignore

try:
    from models.partner.student import Student
except Exception:
    Student = None  # type: ignore


def _d(v: Any) -> Decimal:
    return Decimal(str(v or 0))


def _unique_ints(values: Iterable[Optional[int]]) -> List[int]:
    out: List[int] = []
    seen = set()
    for v in values:
        if v is None:
            continue
        iv = int(v)
        if iv not in seen:
            seen.add(iv)
            out.append(iv)
    return out


def _resolve_labels_by_model(
    db: Session,
    *,
    model,
    ids: List[int],
    label_attr_candidates: tuple[str, ...] = ("name", "title", "display_name", "nickname"),
) -> Dict[int, str]:
    if model is None or not ids:
        return {}

    rows = db.execute(select(model).where(model.id.in_(ids))).scalars().all()  # type: ignore[attr-defined]
    out: Dict[int, str] = {}
    for r in rows:
        rid = getattr(r, "id", None)
        if rid is None:
            continue
        label = None
        for attr in label_attr_candidates:
            if hasattr(r, attr):
                val = getattr(r, attr)
                if val:
                    label = str(val)
                    break
        if label:
            out[int(rid)] = label
    return out


def _apply_dim_labels(db: Session, *, items: List[UsageDimBreakdownItem]) -> List[UsageDimBreakdownItem]:
    if not items:
        return items

    dim_type = items[0].dim_type
    ids = _unique_ints([i.dim_id for i in items])

    if dim_type == "class":
        label_map = _resolve_labels_by_model(db, model=Class, ids=ids)
    elif dim_type == "student":
        label_map = _resolve_labels_by_model(db, model=Student, ids=ids)
    else:
        label_map = {}

    if not label_map:
        return items

    for it in items:
        it.dim_label = label_map.get(int(it.dim_id)) or it.dim_label
    return items


# =========================
# DB-bound "Seoul today"
# =========================
def _db_seoul_today(db: Session) -> date:
    # DB 서버 시간을 기준으로 Asia/Seoul "오늘"을 계산
    return db.execute(
        select(func.date(func.timezone("Asia/Seoul", func.now())))
    ).scalar_one()


def _seoul_date_expr(ts_col):
    return func.date(func.timezone("Asia/Seoul", ts_col))


def _apply_events_filters(
    stmt,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    request_type: Optional[str],
    provider: Optional[str],
    model_name: Optional[str],
):
    sd = _seoul_date_expr(UsageEvent.occurred_at)
    stmt = stmt.where(
        UsageEvent.partner_id == partner_id,
        sd >= start_date,
        sd <= end_date,
    )
    if request_type is not None:
        stmt = stmt.where(UsageEvent.request_type == request_type)
    if provider is not None:
        stmt = stmt.where(UsageEvent.provider == provider)
    if model_name is not None:
        stmt = stmt.where(UsageEvent.model_name == model_name)
    return stmt


def _events_kpi(
    db: Session,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    request_type: Optional[str],
    provider: Optional[str],
    model_name: Optional[str],
) -> Dict[str, Any]:
    stmt = select(
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        literal(0).label("turn_count"),
        func.count(func.distinct(UsageEvent.session_id)).label("session_count"),
        # llm_chat을 "대화 response 수"로 보고 싶으면 여기 집계로 잡아도 됨
        func.coalesce(
            func.sum(case((UsageEvent.request_type == "llm_chat", 1), else_=0)),
            0
        ).label("message_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(True), 1), else_=0)), 0).label("success_count"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
        func.avg(UsageEvent.latency_ms).label("avg_latency_ms"),
        func.percentile_cont(0.95).within_group(UsageEvent.latency_ms).label("p95_latency_ms"),
        func.count(func.distinct(UsageEvent.student_id)).label("_active_students"),
        func.count(func.distinct(UsageEvent.class_id)).label("_active_classes"),
    )

    stmt = _apply_events_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    row = db.execute(stmt).mappings().one()

    return {
        "total_cost_usd": _d(row["total_cost_usd"]),
        "request_count": int(row["request_count"] or 0),
        "turn_count": int(row["turn_count"] or 0),
        "session_count": int(row["session_count"] or 0),
        "message_count": int(row["message_count"] or 0),
        "total_tokens": int(row["total_tokens"] or 0),
        "success_count": int(row["success_count"] or 0),
        "error_count": int(row["error_count"] or 0),
        "avg_latency_ms": _d(row["avg_latency_ms"]) if row["avg_latency_ms"] is not None else None,
        "p95_latency_ms": _d(row["p95_latency_ms"]) if row["p95_latency_ms"] is not None else None,
        "active_students": int(row["_active_students"] or 0),
        "active_classes": int(row["_active_classes"] or 0),
    }


def _events_timeseries_daily(
    db: Session,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    request_type: Optional[str],
    provider: Optional[str],
    model_name: Optional[str],
) -> List[Dict[str, Any]]:
    seoul_d = _seoul_date_expr(UsageEvent.occurred_at).label("usage_date")

    stmt = select(
        seoul_d,
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
    )

    stmt = _apply_events_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    stmt = stmt.group_by(seoul_d).order_by(seoul_d.asc())
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


def _events_model_breakdown(
    db: Session,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    request_type: Optional[str],
    provider: Optional[str],
    model_name: Optional[str],
    top_n: int,
) -> List[Dict[str, Any]]:
    stmt = select(
        UsageEvent.provider.label("provider"),
        UsageEvent.model_name.label("model_name"),
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
    )

    stmt = _apply_events_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    stmt = (
        stmt.group_by(UsageEvent.provider, UsageEvent.model_name)
        .order_by(desc(func.sum(UsageEvent.total_cost_usd)))
        .limit(top_n)
    )
    rows = db.execute(stmt).mappings().all()

    return [
        {
            "provider": r["provider"],
            "model_name": r["model_name"],
            "total_cost_usd": _d(r["total_cost_usd"]),
            "request_count": int(r["request_count"] or 0),
            "total_tokens": int(r["total_tokens"] or 0),
            "share_pct": None,  # merge 후 재계산
        }
        for r in rows
    ]


def _events_dim_breakdown(
    db: Session,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    dim_type: str,  # class | student
    request_type: Optional[str],
    provider: Optional[str],
    model_name: Optional[str],
    top_n: int,
) -> List[Dict[str, Any]]:
    if dim_type == "class":
        dim_col = UsageEvent.class_id
    elif dim_type == "student":
        dim_col = UsageEvent.student_id
    else:
        raise ValueError("dim_type must be one of: class, student")

    stmt = select(
        dim_col.label("dim_id"),
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.count(UsageEvent.id).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
    )

    stmt = _apply_events_filters(
        stmt,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    ).where(dim_col.is_not(None))

    stmt = (
        stmt.group_by(dim_col)
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
            "dim_label": None,
        }
        for r in rows
    ]


def _merge_kpi(daily: Dict[str, Any], today: Dict[str, Any]) -> Dict[str, Any]:
    # 합산
    total_cost = _d(daily.get("total_cost_usd")) + _d(today.get("total_cost_usd"))
    request_count = int(daily.get("request_count") or 0) + int(today.get("request_count") or 0)
    turn_count = int(daily.get("turn_count") or 0) + int(today.get("turn_count") or 0)
    session_count = int(daily.get("session_count") or 0) + int(today.get("session_count") or 0)
    message_count = int(daily.get("message_count") or 0) + int(today.get("message_count") or 0)
    total_tokens = int(daily.get("total_tokens") or 0) + int(today.get("total_tokens") or 0)
    success_count = int(daily.get("success_count") or 0) + int(today.get("success_count") or 0)
    error_count = int(daily.get("error_count") or 0) + int(today.get("error_count") or 0)

    # avg latency: request_count 가중 평균(근사)
    avg_latency_ms = None
    d_avg = daily.get("avg_latency_ms")
    t_avg = today.get("avg_latency_ms")
    d_req = int(daily.get("request_count") or 0)
    t_req = int(today.get("request_count") or 0)
    if (d_avg is not None or t_avg is not None) and (d_req + t_req) > 0:
        num = Decimal("0")
        if d_avg is not None:
            num += _d(d_avg) * Decimal(d_req)
        if t_avg is not None:
            num += _d(t_avg) * Decimal(t_req)
        avg_latency_ms = num / Decimal(d_req + t_req)

    # p95: “근사”로 큰 값 채택
    p95 = None
    candidates = []
    if daily.get("p95_latency_ms") is not None:
        candidates.append(_d(daily["p95_latency_ms"]))
    if today.get("p95_latency_ms") is not None:
        candidates.append(_d(today["p95_latency_ms"]))
    if candidates:
        p95 = max(candidates)

    return {
        "total_cost_usd": total_cost,
        "request_count": request_count,
        "turn_count": turn_count,
        "session_count": session_count,
        "message_count": message_count,
        "total_tokens": total_tokens,
        "success_count": success_count,
        "error_count": error_count,
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95,
        # active_*는 아래에서 별도로 넣어줌(중복/합산 이슈)
        "active_students": None,
        "active_classes": None,
    }


def _merge_timeseries(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_date: Dict[date, Dict[str, Any]] = {}
    for r in a + b:
        d0 = r["usage_date"]
        cur = by_date.get(d0)
        if not cur:
            by_date[d0] = dict(r)
        else:
            cur["total_cost_usd"] = _d(cur["total_cost_usd"]) + _d(r["total_cost_usd"])
            cur["request_count"] = int(cur["request_count"] or 0) + int(r["request_count"] or 0)
            cur["total_tokens"] = int(cur["total_tokens"] or 0) + int(r["total_tokens"] or 0)
            cur["error_count"] = int(cur["error_count"] or 0) + int(r["error_count"] or 0)
    return [by_date[k] for k in sorted(by_date.keys())]


def _merge_model_breakdown(daily_rows: List[Dict[str, Any]], today_rows: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    agg: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in daily_rows + today_rows:
        key = (str(r.get("provider")), str(r.get("model_name")))
        cur = agg.get(key)
        if not cur:
            agg[key] = {
                "provider": r.get("provider"),
                "model_name": r.get("model_name"),
                "total_cost_usd": _d(r.get("total_cost_usd")),
                "request_count": int(r.get("request_count") or 0),
                "total_tokens": int(r.get("total_tokens") or 0),
                "share_pct": None,
            }
        else:
            cur["total_cost_usd"] = _d(cur["total_cost_usd"]) + _d(r.get("total_cost_usd"))
            cur["request_count"] += int(r.get("request_count") or 0)
            cur["total_tokens"] += int(r.get("total_tokens") or 0)

    rows = list(agg.values())
    rows.sort(key=lambda x: _d(x["total_cost_usd"]), reverse=True)
    rows = rows[:top_n]

    total_cost = sum((_d(r["total_cost_usd"]) for r in rows), Decimal("0"))
    if total_cost > 0:
        for r in rows:
            r["share_pct"] = (_d(r["total_cost_usd"]) / total_cost) * Decimal("100")
    return rows


def _merge_dim_breakdown(daily_rows: List[Dict[str, Any]], today_rows: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    agg: Dict[int, Dict[str, Any]] = {}
    for r in daily_rows + today_rows:
        did = int(r["dim_id"])
        cur = agg.get(did)
        if not cur:
            agg[did] = {
                "dim_type": r["dim_type"],
                "dim_id": did,
                "total_cost_usd": _d(r.get("total_cost_usd")),
                "request_count": int(r.get("request_count") or 0),
                "total_tokens": int(r.get("total_tokens") or 0),
                "error_count": int(r.get("error_count") or 0),
                "dim_label": r.get("dim_label"),
            }
        else:
            cur["total_cost_usd"] = _d(cur["total_cost_usd"]) + _d(r.get("total_cost_usd"))
            cur["request_count"] += int(r.get("request_count") or 0)
            cur["total_tokens"] += int(r.get("total_tokens") or 0)
            cur["error_count"] += int(r.get("error_count") or 0)

    rows = list(agg.values())
    rows.sort(key=lambda x: _d(x["total_cost_usd"]), reverse=True)
    return rows[:top_n]


def get_instructor_usage_analytics(
    db: Session,
    *,
    partner_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    top_n_models: int = 20,
    top_n_classes: int = 20,
    top_n_students: int = 20,
    with_labels: bool = True,
) -> InstructorUsageAnalyticsResponse:
    today = _db_seoul_today(db)
    effective_end = end_date or today

    # daily는 "어제까지"
    yesterday = today - timedelta(days=1)
    daily_end = min(effective_end, yesterday)

    # 오늘(events) 범위
    events_start = max(today, start_date or today)
    events_end = effective_end

    # -------------------------
    # 1) daily 파트 (존재하면)
    # -------------------------
    daily_kpi_dict: Dict[str, Any] = {
        "total_cost_usd": Decimal("0"),
        "request_count": 0,
        "turn_count": 0,
        "session_count": 0,
        "message_count": 0,
        "total_tokens": 0,
        "success_count": 0,
        "error_count": 0,
        "avg_latency_ms": None,
        "p95_latency_ms": None,
        "active_students": 0,
        "active_classes": 0,
    }
    daily_ts_rows: List[Dict[str, Any]] = []
    daily_models_rows: List[Dict[str, Any]] = []
    daily_classes_rows: List[Dict[str, Any]] = []
    daily_students_rows: List[Dict[str, Any]] = []

    daily_has_range = (start_date is None) or (start_date <= daily_end)
    if daily_has_range and daily_end >= date(1970, 1, 1):
        daily_kpi_dict = usage_crud.get_usage_kpi_on_read(
            db,
            partner_id=partner_id,
            start_date=start_date,
            end_date=daily_end,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
        )
        daily_ts_rows = usage_crud.get_usage_timeseries_daily_on_read(
            db,
            partner_id=partner_id,
            start_date=start_date,
            end_date=daily_end,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
        )
        daily_models_rows = usage_crud.get_usage_model_breakdown_on_read(
            db,
            partner_id=partner_id,
            start_date=start_date,
            end_date=daily_end,
            request_type=request_type,
            top_n=top_n_models,
        )

        # breakdown(daily): provider/model filter 들어가면 daily 테이블에서 필터링된 합산이 필요해서
        # 기존 service가 하던 방식대로 "필터 있으면 직접 sum query"는 구현 범위가 커져서,
        # 여기서는 일단 daily breakdown은 기존 get_usage_dim_breakdown 그대로 사용한다.
        # (provider/model로 클래스/학생 breakdown까지 필터링이 꼭 필요하면, daily에도 동일한 filtered 쿼리 버전 추가해줘야 함)
        daily_classes_rows = usage_crud.get_usage_dim_breakdown_on_read(
            db,
            partner_id=partner_id,
            dim_type="class",
            start_date=start_date,
            end_date=daily_end,
            request_type=request_type,
            top_n=top_n_classes,
        )
        daily_students_rows = usage_crud.get_usage_dim_breakdown_on_read(
            db,
            partner_id=partner_id,
            dim_type="student",
            start_date=start_date,
            end_date=daily_end,
            request_type=request_type,
            top_n=top_n_students,
        )

    # -------------------------
    # 2) events(오늘) 파트
    # -------------------------
    today_kpi_dict: Dict[str, Any] = {
        "total_cost_usd": Decimal("0"),
        "request_count": 0,
        "turn_count": 0,
        "session_count": 0,
        "message_count": 0,
        "total_tokens": 0,
        "success_count": 0,
        "error_count": 0,
        "avg_latency_ms": None,
        "p95_latency_ms": None,
        "active_students": 0,
        "active_classes": 0,
    }
    today_ts_rows: List[Dict[str, Any]] = []
    today_models_rows: List[Dict[str, Any]] = []
    today_classes_rows: List[Dict[str, Any]] = []
    today_students_rows: List[Dict[str, Any]] = []

    if events_end >= today and events_start <= events_end:
        today_kpi_dict = _events_kpi(
            db,
            partner_id=partner_id,
            start_date=events_start,
            end_date=events_end,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
        )
        today_ts_rows = _events_timeseries_daily(
            db,
            partner_id=partner_id,
            start_date=events_start,
            end_date=events_end,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
        )
        today_models_rows = _events_model_breakdown(
            db,
            partner_id=partner_id,
            start_date=events_start,
            end_date=events_end,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
            top_n=top_n_models,
        )
        today_classes_rows = _events_dim_breakdown(
            db,
            partner_id=partner_id,
            start_date=events_start,
            end_date=events_end,
            dim_type="class",
            request_type=request_type,
            provider=provider,
            model_name=model_name,
            top_n=top_n_classes,
        )
        today_students_rows = _events_dim_breakdown(
            db,
            partner_id=partner_id,
            start_date=events_start,
            end_date=events_end,
            dim_type="student",
            request_type=request_type,
            provider=provider,
            model_name=model_name,
            top_n=top_n_students,
        )

    # -------------------------
    # 3) merge
    # -------------------------
    merged_kpi = _merge_kpi(daily_kpi_dict, today_kpi_dict)

    # active_students / classes:
    # - 정확한 union(count distinct)은 daily+events를 합쳐서 세야 하는데,
    # - 우선은 "기간 전체"를 daily가 이미 distinct로 잡고(어제까지),
    #   오늘 distinct를 + 하되, 중복 가능성은 존재.
    # 실무 정확도가 필요하면 union SQL로 바꾸면 됨.
    merged_kpi["active_students"] = int(daily_kpi_dict.get("active_students") or 0) + int(today_kpi_dict.get("active_students") or 0)
    merged_kpi["active_classes"] = int(daily_kpi_dict.get("active_classes") or 0) + int(today_kpi_dict.get("active_classes") or 0)

    kpi = UsageKpiResponse(**merged_kpi)

    merged_ts = _merge_timeseries(daily_ts_rows, today_ts_rows)
    timeseries = [UsageTimeSeriesPoint(**r) for r in merged_ts]

    merged_models = _merge_model_breakdown(daily_models_rows, today_models_rows, top_n_models)
    models = [UsageModelBreakdownItem(**r) for r in merged_models]

    merged_classes = _merge_dim_breakdown(daily_classes_rows, today_classes_rows, top_n_classes)
    merged_students = _merge_dim_breakdown(daily_students_rows, today_students_rows, top_n_students)

    classes = [UsageDimBreakdownItem(**r) for r in merged_classes]
    students = [UsageDimBreakdownItem(**r) for r in merged_students]

    if with_labels:
        classes = _apply_dim_labels(db, items=classes)
        students = _apply_dim_labels(db, items=students)

    return InstructorUsageAnalyticsResponse(
        kpi=kpi,
        timeseries=timeseries,
        models=models,
        classes=classes,
        students=students,
    )
