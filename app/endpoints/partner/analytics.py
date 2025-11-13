# app/endpoints/partner/analytics.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_admin
from crud.partner import analytics as analytics_crud
from schemas.partner.analytics import (
    AnalyticsSnapshotResponse,
    AnalyticsSnapshotPage,
    EnrollmentFinanceMonthlyResponse,
    EnrollmentFinanceMonthlyPage,
)

router = APIRouter()  # prefix는 routers.py에서 설정


# ==============================
# analytics_snapshots (READ-ONLY)
# ==============================

@router.get("/snapshots", response_model=AnalyticsSnapshotPage)
def list_analytics_snapshots(
    partner_id: int = Path(..., ge=1),
    metric_type: Optional[str] = Query(None, description="지표 타입 (예: active_students_7d)"),
    date_from: Optional[date] = Query(None, description="시작 일자"),
    date_to: Optional[date] = Query(None, description="종료 일자"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = analytics_crud.list_analytics_snapshots(
        db,
        partner_id=partner_id,
        metric_type=metric_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    items = [AnalyticsSnapshotResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/snapshots/{snapshot_id}", response_model=AnalyticsSnapshotResponse)
def get_analytics_snapshot(
    partner_id: int = Path(..., ge=1),
    snapshot_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = analytics_crud.get_analytics_snapshot(db, snapshot_id=snapshot_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="snapshot not found")
    return AnalyticsSnapshotResponse.model_validate(obj)


# ==============================
# enrollment_finance_monthly (READ-ONLY)
# ==============================

@router.get("/enrollment-finance", response_model=EnrollmentFinanceMonthlyPage)
def list_enrollment_finance_monthly(
    partner_id: int = Path(..., ge=1),
    enrollment_id: Optional[int] = Query(None, description="특정 enrollment_id 필터"),
    month_from: Optional[date] = Query(None, description="YYYY-MM-01 시작 (포함)"),
    month_to: Optional[date] = Query(None, description="YYYY-MM-01 종료 (포함)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = analytics_crud.list_enrollment_finance_monthly(
        db,
        partner_id=partner_id,
        enrollment_id=enrollment_id,
        month_from=month_from,
        month_to=month_to,
        page=page,
        size=size,
    )
    items = [EnrollmentFinanceMonthlyResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/enrollment-finance/{efm_id}", response_model=EnrollmentFinanceMonthlyResponse)
def get_enrollment_finance_monthly(
    partner_id: int = Path(..., ge=1),
    efm_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = analytics_crud.get_enrollment_finance_monthly(db, efm_id=efm_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="enrollment_finance_monthly not found")
    return EnrollmentFinanceMonthlyResponse.model_validate(obj)
