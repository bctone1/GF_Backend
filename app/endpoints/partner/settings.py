# app/endpoints/partner/settings.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from models.partner.partner_core import Partner

from schemas.partner.settings import (
    PartnerSettingsResponse,
    ProfileSettings,
    ProfileUpdateRequest,
    NotificationSettings,
    NotificationUpdateRequest,
)
from service.partner.settings import get_partner_settings
import crud.partner.partner_core as partner_core_crud
import crud.partner.notify as notify_crud

router = APIRouter()


@router.get(
    "",
    response_model=PartnerSettingsResponse,
    summary="통합 설정 조회",
)
def read_settings(
    partner_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
) -> PartnerSettingsResponse:
    return get_partner_settings(db, partner=current_partner)


@router.patch(
    "/profile",
    response_model=ProfileSettings,
    summary="프로필 수정",
)
def update_profile(
    partner_id: int = Path(..., ge=1),
    payload: ProfileUpdateRequest = ...,
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
) -> ProfileSettings:
    fields = payload.model_dump(exclude_unset=True)
    updated = partner_core_crud.update_partner(db, current_partner.id, **fields)

    org_name = ""
    if current_partner.org:
        org_name = current_partner.org.name
    else:
        from models.partner.partner_core import Org
        org = db.get(Org, current_partner.org_id)
        org_name = org.name if org else ""

    return ProfileSettings(
        partner_id=updated.id,
        full_name=updated.full_name,
        email=updated.email,
        phone=updated.phone,
        org_name=org_name,
        role=updated.role,
    )


@router.put(
    "/notifications",
    response_model=NotificationSettings,
    summary="알림 설정 일괄 수정",
)
def update_notifications(
    partner_id: int = Path(..., ge=1),
    payload: NotificationUpdateRequest = ...,
    db: Session = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner_user),
) -> NotificationSettings:
    data = payload.model_dump(exclude_unset=True)
    pref = notify_crud.upsert_notification_pref_for_user(
        db,
        partner_user_id=current_partner.id,
        data=data,
    )
    return NotificationSettings(
        new_student_email=pref.new_student_email,
        class_deadline_email=pref.class_deadline_email,
        settlement_email=pref.settlement_email,
        api_cost_alert_email=pref.api_cost_alert_email,
        system_notice=pref.system_notice,
        marketing_opt_in=pref.marketing_opt_in,
    )
