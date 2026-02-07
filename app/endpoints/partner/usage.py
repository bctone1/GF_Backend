# app/endpoints/partner/usage.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from models.partner.partner_core import Partner

from schemas.partner.usage import (
    InstructorUsageAnalyticsResponse,
    UsageEventResponse,
    UsageDailyResponse,
    FeatureUsageResponse,
)
from service.partner.instructor_analytics import get_instructor_usage_analytics
from service.partner.feature_usage import get_feature_usage as feature_usage_svc
import crud.partner.usage as usage_crud

router = APIRouter()


@router.get(
    "",
    response_model=InstructorUsageAnalyticsResponse,
    summary="강사 사용량 통계(페이지용 통합 응답)",
)
def read_instructor_usage_analytics(
    partner_id: int,
    *,
    db: Session = Depends(get_db),
    me : Partner = Depends(get_current_partner_user),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    request_type: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    model_name: Optional[str] = Query(default=None),
    top_n_models: int = Query(default=20, ge=1, le=100),
    top_n_classes: int = Query(default=20, ge=1, le=200),
    top_n_students: int = Query(default=20, ge=1, le=200),
    with_labels: bool = Query(default=True),
) -> InstructorUsageAnalyticsResponse:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    return get_instructor_usage_analytics(
        db,
        partner_id=me.org_id,
        start_date=start_date,
        end_date=end_date,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
        top_n_models=top_n_models,
        top_n_classes=top_n_classes,
        top_n_students=top_n_students,
        with_labels=with_labels,
    )


@router.get(
    "/features",
    response_model=FeatureUsageResponse,
    summary="기능 활용 현황 (비교모드, RAG, 프로젝트)",
)
def get_feature_usage_stats(
    partner_id: int,
    *,
    db: Session = Depends(get_db),
    me: Partner = Depends(get_current_partner_user),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
) -> FeatureUsageResponse:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    return feature_usage_svc(
        db,
        partner=me,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/events",
    response_model=List[UsageEventResponse],
    summary="사용량 원천 이벤트 로그 조회(드릴다운/디버깅)",
)
def list_usage_events(
    partner_id: int,
    *,
    db: Session = Depends(get_db),
    me: Partner = Depends(get_current_partner_user),
    start_at: Optional[datetime] = Query(default=None, description="시작 시각(포함)"),
    end_at: Optional[datetime] = Query(default=None, description="종료 시각(미만)"),
    request_type: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    model_name: Optional[str] = Query(default=None),
    class_id: Optional[int] = Query(default=None),
    enrollment_id: Optional[int] = Query(default=None),
    student_id: Optional[int] = Query(default=None),
    success: Optional[bool] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    newest_first: bool = Query(default=True),
) -> List[UsageEventResponse]:
    if start_at and end_at and end_at <= start_at:
        raise HTTPException(status_code=400, detail="end_at must be > start_at")

    rows = usage_crud.list_usage_events(
        db,
        partner_id=me.org_id,
        start_at=start_at,
        end_at=end_at,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
        class_id=class_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        success=success,
        offset=offset,
        limit=limit,
        newest_first=newest_first,
    )
    return [UsageEventResponse.model_validate(r) for r in rows]


@router.get(
    "/daily",
    response_model=List[UsageDailyResponse],
    summary="일 단위 집계 조회(차트/테이블용 원본)",
)
def list_usage_daily(
    partner_id: int,
    *,
    db: Session = Depends(get_db),
    me: Partner = Depends(get_current_partner_user),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    dim_type: Optional[str] = Query(default=None, description="partner/class/enrollment/student"),
    dim_id: Optional[int] = Query(default=None),
    request_type: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    model_name: Optional[str] = Query(default=None),
) -> List[UsageDailyResponse]:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    rows = usage_crud.list_usage_daily_rows(
        db,
        partner_id=me.org_id,
        start_date=start_date,
        end_date=end_date,
        dim_type=dim_type,
        dim_id=dim_id,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
    )
    return [UsageDailyResponse.model_validate(r) for r in rows]
