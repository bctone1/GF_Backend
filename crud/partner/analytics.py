# crud/partner/analytics.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from models.partner.analytics import (
    AnalyticsSnapshot,
    EnrollmentFinanceMonthly,
)


# =============================================================================
# AnalyticsSnapshot (READ-ONLY: ETL이 적재)
# =============================================================================

def get_analytics_snapshot(
    db: Session,
    snapshot_id: int,
) -> Optional[AnalyticsSnapshot]:
    """
    ID 기준 단건 조회.
    """
    return db.get(AnalyticsSnapshot, snapshot_id)


def list_analytics_snapshots(
    db: Session,
    *,
    partner_id: int,
    metric_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[AnalyticsSnapshot], int]:
    """
    파트너별 일간 스냅샷 목록 조회.

    - metric_type: 특정 지표만 필터링 (예: 'active_students_7d')
    - date_from/date_to: 스냅샷 날짜 범위 필터
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [AnalyticsSnapshot.partner_id == partner_id]

    if metric_type is not None:
        filters.append(AnalyticsSnapshot.metric_type == metric_type)
    if date_from is not None:
        filters.append(AnalyticsSnapshot.snapshot_date >= date_from)
    if date_to is not None:
        filters.append(AnalyticsSnapshot.snapshot_date <= date_to)

    base_stmt: Select[AnalyticsSnapshot] = select(AnalyticsSnapshot).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt
        .order_by(
            AnalyticsSnapshot.snapshot_date.desc(),
            AnalyticsSnapshot.metric_type.asc(),
            AnalyticsSnapshot.id.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_analytics_snapshot(
    db: Session,
    *,
    data: Dict[str, Any],
) -> AnalyticsSnapshot:
    """
    ETL/스케줄러 전용: analytics_snapshots 삽입.
    - 일반 애플리케이션 코드에서 직접 호출하는 것은 권장하지 않음.
    """
    obj = AnalyticsSnapshot(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_analytics_snapshot(
    db: Session,
    *,
    snapshot: AnalyticsSnapshot,
    data: Dict[str, Any],
) -> AnalyticsSnapshot:
    """
    ETL 재집계 상황 등에서의 수정 용도.
    """
    for key, value in data.items():
        setattr(snapshot, key, value)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_analytics_snapshot(
    db: Session,
    *,
    snapshot: AnalyticsSnapshot,
) -> None:
    """
    잘못 적재된 스냅샷 정리용.
    """
    db.delete(snapshot)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/analytics.py 예시)
#
# def upsert_analytics_snapshot(
#     db: Session,
#     *,
#     partner_id: int,
#     snapshot_date: date,
#     metric_type: str,
#     metric_value: Decimal,
#     meta: dict[str, Any] | None = None,
# ) -> AnalyticsSnapshot:
#     """
#     1) (partner_id, snapshot_date, metric_type) 기준으로 기존 레코드 조회
#     2) 있으면 업데이트, 없으면 생성
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# EnrollmentFinanceMonthly (READ-ONLY: ETL이 적재)
# =============================================================================

def get_enrollment_finance_monthly(
    db: Session,
    efm_id: int,
) -> Optional[EnrollmentFinanceMonthly]:
    """
    ID 기준 단건 조회.
    """
    return db.get(EnrollmentFinanceMonthly, efm_id)


def list_enrollment_finance_monthly(
    db: Session,
    *,
    partner_id: int,
    enrollment_id: Optional[int] = None,
    month_from: Optional[date] = None,
    month_to: Optional[date] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[EnrollmentFinanceMonthly], int]:
    """
    수강(enrollment) 단위 월간 재무 집계 목록.

    - partner_id: 파트너 스코프 강제
    - enrollment_id: 특정 수강만 보고 싶을 때
    - month_from/month_to: YYYY-MM-01 범위 필터
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [EnrollmentFinanceMonthly.partner_id == partner_id]

    if enrollment_id is not None:
        filters.append(EnrollmentFinanceMonthly.enrollment_id == enrollment_id)
    if month_from is not None:
        filters.append(EnrollmentFinanceMonthly.month >= month_from)
    if month_to is not None:
        filters.append(EnrollmentFinanceMonthly.month <= month_to)

    base_stmt: Select[EnrollmentFinanceMonthly] = select(EnrollmentFinanceMonthly).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt
        .order_by(
            EnrollmentFinanceMonthly.enrollment_id.asc(),
            EnrollmentFinanceMonthly.month.desc(),
            EnrollmentFinanceMonthly.id.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_enrollment_finance_monthly(
    db: Session,
    *,
    data: Dict[str, Any],
) -> EnrollmentFinanceMonthly:
    """
    ETL/스케줄러 전용: enrollment_finance_monthly 삽입.
    """
    obj = EnrollmentFinanceMonthly(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_enrollment_finance_monthly(
    db: Session,
    *,
    efm: EnrollmentFinanceMonthly,
    data: Dict[str, Any],
) -> EnrollmentFinanceMonthly:
    """
    집계 재계산 시 수정 용도.
    """
    for key, value in data.items():
        setattr(efm, key, value)
    db.add(efm)
    db.commit()
    db.refresh(efm)
    return efm


def delete_enrollment_finance_monthly(
    db: Session,
    *,
    efm: EnrollmentFinanceMonthly,
) -> None:
    db.delete(efm)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/analytics.py 예시)
#
# def recompute_enrollment_finance_monthly(
#     db: Session,
#     *,
#     partner_id: int,
#     enrollment_id: int,
#     month: date,
# ) -> EnrollmentFinanceMonthly:
#     """
#     1) usage_daily / api_cost_daily / invoice_items 등을 기반으로
#        해당 enrollment, month 에 대한 재무 수치를 재계산
#     2) enrollment_finance_monthly upsert
#     """
#     ...
# -----------------------------------------------------------------------------
