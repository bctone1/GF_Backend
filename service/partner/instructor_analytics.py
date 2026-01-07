# service/partner/instructor_analytics.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Dict, List, Any, Iterable

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

import crud.partner.usage as usage_crud
from models.partner.usage import UsageDaily

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
    """
    모델이 존재하면 id -> label 을 조인해서 채움.
    없거나 컬럼명이 다르면 빈 dict.
    """
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


# =========================
# filtered breakdown helper (provider/model_name까지 반영)
# =========================
def _get_usage_dim_breakdown_filtered(
    db: Session,
    *,
    partner_id: int,
    dim_type: str,  # "class" | "student" | "enrollment"
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    request_type: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    top_n: int = 20,
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
    if end_date is not None:
        stmt = stmt.where(UsageDaily.usage_date <= end_date)

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


def _apply_dim_labels(
    db: Session,
    *,
    items: List[UsageDimBreakdownItem],
) -> List[UsageDimBreakdownItem]:
    """
    dim_label 채우기(가능할 때만).
    - class -> Class (name/title 등)
    - student -> Student (name/nickname 등)
    """
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
# public service
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
    instructor-analytics 페이지용 통합 서비스.

    - KPI/추이는 중복 방지를 위해 usage_daily.dim_type='partner'만 사용
    - 클래스/학생 breakdown은 dim_type='class'/'student'를 합산해서 랭킹
    - provider/model_name 필터가 들어오면 breakdown도 동일 필터를 반영
    """

    # 1) KPI
    kpi_dict = usage_crud.get_usage_kpi(
        db,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )
    kpi = UsageKpiResponse(**kpi_dict)

    # 2) Timeseries (daily)
    ts_rows = usage_crud.get_usage_timeseries_daily(
        db,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )
    timeseries = [UsageTimeSeriesPoint(**r) for r in ts_rows]

    # 3) Model breakdown
    models_rows = usage_crud.get_usage_model_breakdown(
        db,
        partner_id=partner_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        top_n=top_n_models,
    )

    # provider/model_name 필터가 들어오면 결과를 좁히고 share 재계산
    if provider is not None:
        models_rows = [r for r in models_rows if r.get("provider") == provider]
    if model_name is not None:
        models_rows = [r for r in models_rows if r.get("model_name") == model_name]

    if models_rows:
        total_cost = sum((_d(r.get("total_cost_usd")) for r in models_rows), Decimal("0"))
        for r in models_rows:
            if total_cost > 0:
                r["share_pct"] = (_d(r.get("total_cost_usd")) / total_cost) * Decimal("100")
            else:
                r["share_pct"] = None

    models = [UsageModelBreakdownItem(**r) for r in models_rows]

    # 4) Class / Student breakdown
    if provider is None and model_name is None:
        classes_rows = usage_crud.get_usage_dim_breakdown(
            db,
            partner_id=partner_id,
            dim_type="class",
            start_date=start_date,
            end_date=end_date,
            request_type=request_type,
            top_n=top_n_classes,
        )
        students_rows = usage_crud.get_usage_dim_breakdown(
            db,
            partner_id=partner_id,
            dim_type="student",
            start_date=start_date,
            end_date=end_date,
            request_type=request_type,
            top_n=top_n_students,
        )
    else:
        # provider/model_name까지 반영한 breakdown
        classes_rows = _get_usage_dim_breakdown_filtered(
            db,
            partner_id=partner_id,
            dim_type="class",
            start_date=start_date,
            end_date=end_date,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
            top_n=top_n_classes,
        )
        students_rows = _get_usage_dim_breakdown_filtered(
            db,
            partner_id=partner_id,
            dim_type="student",
            start_date=start_date,
            end_date=end_date,
            request_type=request_type,
            provider=provider,
            model_name=model_name,
            top_n=top_n_students,
        )

    classes = [UsageDimBreakdownItem(**r) for r in classes_rows]
    students = [UsageDimBreakdownItem(**r) for r in students_rows]

    # 5) Optional labels (join to class/student tables)
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
