# app/endpoints/partner/dashboard.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from models.partner.partner_core import Partner
from schemas.partner.dashboard import DashboardResponse
from service.partner.dashboard import get_partner_dashboard

router = APIRouter()


@router.get(
    "",
    response_model=DashboardResponse,
    summary="파트너 대시보드 통합 응답",
)
def read_partner_dashboard(
    partner_id: int,
    *,
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
    activity_limit: int = Query(default=10, ge=1, le=50),
    top_students_limit: int = Query(default=5, ge=1, le=20),
) -> DashboardResponse:
    return get_partner_dashboard(
        db,
        partner=current_partner,
        activity_limit=activity_limit,
        top_students_limit=top_students_limit,
    )
