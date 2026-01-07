# service/partner/instructor_analytics.py
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Iterable, Tuple

from sqlalchemy import select, func, desc, case, literal_column
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


def _apply_dim_labels(
    db: Session,
    *,
    items: List[UsageDimBreakdownItem],
) -> List[UsageDimBreakdownItem]:
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

    # pydantic 모델이 freeze 설정일 수도 있으니 안전하게 copy
    return [
        it.model_copy(update={"dim_label": label_map.get(int(it.dim_id)) or it.dim_label})
        for it in items
    ]


# =========================
# DB time bounds (Seoul today)
# - DB가 "지금"을 기준으로 Asia/Seoul의 '오늘 날짜'와
#   그 날짜의 00:00 ~ 내일 00:00 을 UTC timestamptz로 계산
# =========================
def _db_seoul_today_bounds(db: Session) -> Tuple[date, Any, Any]:
    seoul_today_expr = literal_column("timezone('Asia/Seoul', now())::date").label("seoul_today")
    start_utc_expr = literal_column(
        "(timezone('Asia/Seoul', now())::date)::timestamp AT TIME ZONE 'Asia/Seoul'"
    ).label("start_utc")
    end_utc_expr = literal_column(
        "((timezone('Asia/Seoul', now())::date + 1)::timestamp AT TIME ZONE 'Asia/Seoul')"
    ).label("end_utc")

    row = db.execute(select(seoul_today_expr, start_utc_expr, end_utc_expr)).mappings().one()
    return row["seoul_today"], row["start_utc"], row["end_utc"]


# =========================
# 오늘(events) KPI / breakdown
# =========================
def _today_events_kpi(
    db: Session,
    *,
    partner_id: int,
    start_utc,
    end_utc,
    request_type: Optional[str],
    provider: Optional[str],
    model_name: Optional[str],
) -> Dict[str, Any]:
    stmt = select(
        func.coalesce(func.sum(UsageEvent.total_cost_usd), 0).label("total_cost_usd"),
        func.coalesce(func.count(UsageEvent.id), 0).label("request_count"),
        func.coalesce(func.count(func.distinct(UsageEvent.turn_id)), 0).label("turn_count"),
        func.coalesce(func.count(func.distinct(UsageEvent.session_id)), 0).label("session_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(True), 1), else_=0)), 0).label("success_count"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
        func.coalesce(func.count(func.distinct(UsageEvent.student_id)), 0).label("active_students_today"),
        func.coalesce(func.count(func.distinct(UsageEvent.class_id)), 0).label("active_classes_today"),
        func.avg(UsageEvent.latency_ms).label("avg_latency_ms"),
        func.max(UsageEvent.latency_ms).label("p95_latency_ms_approx"),  # 근사(정확 p95는 percentile_cont 필요)
    ).where(
        UsageEvent.partner_id == partner_id,
        UsageEvent.occurred_at >= start_utc,
        UsageEvent.occurred_at < end_utc,
    )

    if request_type is not None:
        stmt = stmt.where(UsageEvent.request_type == request_type)
    if provider is not None:
        stmt = stmt.where(UsageEvent.provider == provider)
    if model_name is not None:
        stmt = stmt.where(UsageEvent.model_name == model_name)

    return dict(db.execute(stmt).mappings().one())


def _today_events_dim_cost(
    db: Session,
    *,
    partner_id: int,
    dim_type: str,  # "class" | "student"
    start_utc,
    end_utc,
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
        func.coalesce(func.count(UsageEvent.id), 0).label("request_count"),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0).label("error_count"),
    ).where(
        UsageEvent.partner_id == partner_id,
        UsageEvent.occurred_at >= start_utc,
        UsageEvent.occurred_at < end_utc,
        dim_col.is_not(None),
    )

    if request_type is not None:
        stmt = stmt.where(UsageEvent.request_type == request_type)
    if provider is not None:
        stmt = stmt.where(UsageEvent.provider == provider)
    if model_name is not None:
        stmt = stmt.where(UsageEvent.model_name == model_name)

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


def _merge_dim_rows(
    base_rows: List[Dict[str, Any]],
    add_rows: List[Dict[str, Any]],
    *,
    top_n: int,
) -> List[Dict[str, Any]]:
    merged: Dict[int, Dict[str, Any]] = {}

    for r in base_rows:
        merged[int(r["dim_id"])] = dict(r)

    for r in add_rows:
        did = int(r["dim_id"])
        if did not in merged:
            merged[did] = dict(r)
            continue

        merged[did]["total_cost_usd"] = _d(merged[did].get("total_cost_usd")) + _d(r.get("total_cost_usd"))
        merged[did]["request_count"] = int(merged[did].get("request_count") or 0) + int(r.get("request_count") or 0)
        merged[did]["total_tokens"] = int(merged[did].get("total_tokens") or 0) + int(r.get("total_tokens") or 0)
        merged[did]["error_count"] = int(merged[did].get("error_count") or 0) + int(r.get("error_count") or 0)

    out = sorted(merged.values(), key=lambda x: _d(x.get("total_cost_usd")), reverse=True)
    return out[:top_n]


# =========================
# public service (hybrid)
# =========================
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
    """
    하이브리드:
    - usage_daily: 어제까지(Seoul 기준)
    - usage_events: 오늘(Seoul 00:00~24:00)만 즉시 집계해서 합산

    사용자가 원하는 핵심 지표:
    - 비용: total_cost_usd
    - 총대화 response 수: request_count
    - 현재 진행중 학생수: (오늘 events에서 distinct student_id)
    - 클래스별 사용 비용: classes breakdown (어제까지 daily + 오늘 events 합쳐 랭킹)
    """

    seoul_today, today_start_utc, today_end_utc = _db_seoul_today_bounds(db)

    includes_today = (
        (start_date is None or start_date <= seoul_today)
        and (end_date is None or end_date >= seoul_today)
    )

    # -------------------------
    # 1) daily는 어제까지로 잘라서 조회
    # -------------------------
    daily_end = end_date
    if includes_today:
        daily_end = seoul_today - timedelta(days=1)

    # KPI (daily)
    kpi_dict = usage_crud.get_usage_kpi(
        db,
        partner_id=partner_id,
        start_date=start_date,
        end_date=daily_end,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    # Timeseries (daily)
    ts_rows = usage_crud.get_usage_timeseries_daily(
        db,
        partner_id=partner_id,
        start_date=start_date,
        end_date=daily_end,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )

    # Model breakdown (daily) - 후보를 넉넉히 가져와서 today와 merge 후 top_n
    models_rows = usage_crud.get_usage_model_breakdown(
        db,
        partner_id=partner_id,
        start_date=start_date,
        end_date=daily_end,
        request_type=request_type,
        top_n=max(top_n_models * 3, top_n_models),
    )

    # Class / Student breakdown (daily) - 후보를 넉넉히
    if provider is None and model_name is None:
        classes_rows = usage_crud.get_usage_dim_breakdown(
            db,
            partner_id=partner_id,
            dim_type="class",
            start_date=start_date,
            end_date=daily_end,
            request_type=request_type,
            top_n=max(top_n_classes * 3, top_n_classes),
        )
        students_rows = usage_crud.get_usage_dim_breakdown(
            db,
            partner_id=partner_id,
            dim_type="student",
            start_date=start_date,
            end_date=daily_end,
            request_type=request_type,
            top_n=max(top_n_students * 3, top_n_students),
        )
    else:
        # provider/model_name 필터까지 포함해서 daily에서 가져옴
        def _get_usage_dim_breakdown_filtered_daily(
            dim_type: str,
            top_n: int,
        ) -> List[Dict[str, Any]]:
            stmt = (
                select(
                    UsageDaily.dim_id.label("dim_id"),
                    func.coalesce(func.sum(UsageDaily.total_cost_usd), 0).label("total_cost_usd"),
                    func.coalesce(func.sum(UsageDaily.request_count), 0).label("request_count"),
                    func.coalesce(func.sum(UsageDaily.total_tokens), 0).label("total_tokens"),
                    func.coalesce(func.sum(UsageDaily.error_count), 0).label("error_count"),
                )
                .where(
                    UsageDaily.partner_id == partner_id,
                    UsageDaily.dim_type == dim_type,
                )
            )

            if start_date is not None:
                stmt = stmt.where(UsageDaily.usage_date >= start_date)
            if daily_end is not None:
                stmt = stmt.where(UsageDaily.usage_date <= daily_end)

            if request_type is not None:
                stmt = stmt.where(UsageDaily.request_type == request_type)
            if provider is not None:
                stmt = stmt.where(UsageDaily.provider == provider)
            if model_name is not None:
                stmt = stmt.where(UsageDaily.model_name == model_name)

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
                    "dim_label": None,
                }
                for r in rows
            ]

        classes_rows = _get_usage_dim_breakdown_filtered_daily("class", max(top_n_classes * 3, top_n_classes))
        students_rows = _get_usage_dim_breakdown_filtered_daily("student", max(top_n_students * 3, top_n_students))

    # -------------------------
    # 2) 오늘(events) 보정
    # -------------------------
    if includes_today:
        today_kpi = _today_events_kpi(
            db,
            partner_id=partner_id,
            start_utc=today_start_utc,
            end_utc=today_end_utc,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
        )

        # KPI 합산 (핵심: 비용/response 수)
        kpi_dict["total_cost_usd"] = _d(kpi_dict.get("total_cost_usd")) + _d(today_kpi.get("total_cost_usd"))
        kpi_dict["request_count"] = int(kpi_dict.get("request_count") or 0) + int(today_kpi.get("request_count") or 0)
        kpi_dict["turn_count"] = int(kpi_dict.get("turn_count") or 0) + int(today_kpi.get("turn_count") or 0)
        kpi_dict["session_count"] = int(kpi_dict.get("session_count") or 0) + int(today_kpi.get("session_count") or 0)
        kpi_dict["total_tokens"] = int(kpi_dict.get("total_tokens") or 0) + int(today_kpi.get("total_tokens") or 0)
        kpi_dict["success_count"] = int(kpi_dict.get("success_count") or 0) + int(today_kpi.get("success_count") or 0)
        kpi_dict["error_count"] = int(kpi_dict.get("error_count") or 0) + int(today_kpi.get("error_count") or 0)

        # ✅ "현재 진행중 학생수"는 오늘 기준으로 오버라이드
        kpi_dict["active_students"] = int(today_kpi.get("active_students_today") or 0)
        kpi_dict["active_classes"] = int(today_kpi.get("active_classes_today") or 0)

        # latency는 근사 (daily의 근사 + today 평균을 단순 가중 평균)
        daily_avg = kpi_dict.get("avg_latency_ms")
        today_avg = today_kpi.get("avg_latency_ms")
        daily_req = int(kpi_dict.get("request_count") or 0) - int(today_kpi.get("request_count") or 0)
        today_req = int(today_kpi.get("request_count") or 0)

        avg_latency_ms = None
        if daily_avg is not None and today_avg is not None and (daily_req + today_req) > 0:
            avg_latency_ms = (_d(daily_avg) * _d(daily_req) + _d(today_avg) * _d(today_req)) / _d(daily_req + today_req)
        elif daily_avg is not None:
            avg_latency_ms = daily_avg
        elif today_avg is not None:
            avg_latency_ms = _d(today_avg)

        kpi_dict["avg_latency_ms"] = avg_latency_ms
        # p95는 정확 결합이 어려워서 기존 근사 유지(필요하면 events에서 percentile_cont 추가)
        # kpi_dict["p95_latency_ms"]는 기존 값 유지

        # Timeseries에 오늘 포인트 추가
        ts_rows.append(
            {
                "usage_date": seoul_today,
                "total_cost_usd": _d(today_kpi.get("total_cost_usd")),
                "request_count": int(today_kpi.get("request_count") or 0),
                "total_tokens": int(today_kpi.get("total_tokens") or 0),
                "error_count": int(today_kpi.get("error_count") or 0),
            }
        )
        ts_rows = sorted(ts_rows, key=lambda r: r["usage_date"])

        # Class 비용(오늘) + daily(어제까지) merge 후 top_n
        today_classes_rows = _today_events_dim_cost(
            db,
            partner_id=partner_id,
            dim_type="class",
            start_utc=today_start_utc,
            end_utc=today_end_utc,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
            top_n=max(top_n_classes * 3, top_n_classes),
        )
        classes_rows = _merge_dim_rows(classes_rows, today_classes_rows, top_n=top_n_classes)

        # Student 비용도 today까지 반영 (페이지에 쓰이면 유용)
        today_students_rows = _today_events_dim_cost(
            db,
            partner_id=partner_id,
            dim_type="student",
            start_utc=today_start_utc,
            end_utc=today_end_utc,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
            top_n=max(top_n_students * 3, top_n_students),
        )
        students_rows = _merge_dim_rows(students_rows, today_students_rows, top_n=top_n_students)

        # 모델 breakdown은 여기선 "오늘 미반영"이어도 핵심 KPI에는 영향 없지만,
        # UX 일관성을 위해 필요한 경우 events 기반 모델 집계를 추가하면 됨.

    # -------------------------
    # 3) model breakdown 필터/점유율 재계산 + top_n
    # -------------------------
    if provider is not None:
        models_rows = [r for r in models_rows if r.get("provider") == provider]
    if model_name is not None:
        models_rows = [r for r in models_rows if r.get("model_name") == model_name]

    models_rows = sorted(models_rows, key=lambda r: _d(r.get("total_cost_usd")), reverse=True)[:top_n_models]

    if models_rows:
        total_cost = sum((_d(r.get("total_cost_usd")) for r in models_rows), Decimal("0"))
        for r in models_rows:
            r["share_pct"] = (_d(r.get("total_cost_usd")) / total_cost) * Decimal("100") if total_cost > 0 else None

    # -------------------------
    # 4) schema 변환
    # -------------------------
    kpi = UsageKpiResponse(**kpi_dict)
    timeseries = [UsageTimeSeriesPoint(**r) for r in ts_rows]
    models = [UsageModelBreakdownItem(**r) for r in models_rows]

    classes = [UsageDimBreakdownItem(**r) for r in classes_rows]
    students = [UsageDimBreakdownItem(**r) for r in students_rows]

    # 5) Optional labels
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
