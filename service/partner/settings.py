# service/partner/settings.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.partner.partner_core import Partner, Org
from models.partner.catalog import ModelCatalog, OrgLlmSetting
from models.partner.notify import NotificationPreference
from models.partner.usage import UsageEvent

from schemas.partner.settings import (
    PartnerSettingsResponse,
    ProfileSettings,
    AiModelSettings,
    ModelSettingItem,
    NotificationSettings,
    PricingInfo,
)

PLATFORM_FEE_RATE = Decimal("0.15")


def _seoul_date_expr(ts_col):
    """Helper: convert a timestamptz column to Seoul date."""
    return func.date(func.timezone("Asia/Seoul", ts_col))


def get_partner_settings(
    db: Session,
    *,
    partner: Partner,
) -> PartnerSettingsResponse:
    """Settings 페이지 통합 조회."""

    # ── 1. profile ──
    org: Optional[Org] = db.get(Org, partner.org_id)
    org_name = org.name if org else ""

    profile = ProfileSettings(
        partner_id=partner.id,
        full_name=partner.full_name,
        email=partner.email,
        phone=partner.phone,
        org_name=org_name,
        role=partner.role,
    )

    # ── 2. ai_models ──
    org_setting: Optional[OrgLlmSetting] = db.execute(
        select(OrgLlmSetting).where(OrgLlmSetting.org_id == partner.org_id)
    ).scalar_one_or_none()

    # available chat models
    models_rows = db.execute(
        select(ModelCatalog)
        .where(ModelCatalog.is_active.is_(True), ModelCatalog.modality == "chat")
        .order_by(ModelCatalog.provider, ModelCatalog.model_name)
    ).scalars().all()

    available_models: List[ModelSettingItem] = [
        ModelSettingItem(
            model_id=m.id,
            provider=m.provider,
            model_name=m.model_name,
            modality=m.modality,
            is_active=m.is_active,
            default_pricing=m.default_pricing,
        )
        for m in models_rows
    ]

    ai_models = AiModelSettings(
        default_chat_model=org_setting.default_chat_model if org_setting else None,
        enable_parallel_mode=org_setting.enable_parallel_mode if org_setting else False,
        daily_message_limit=org_setting.daily_message_limit if org_setting else None,
        token_alert_threshold=org_setting.token_alert_threshold if org_setting else None,
        available_models=available_models,
    )

    # ── 3. notifications ──
    pref: Optional[NotificationPreference] = db.execute(
        select(NotificationPreference)
        .where(NotificationPreference.partner_user_id == partner.id)
    ).scalar_one_or_none()

    if pref:
        notifications = NotificationSettings(
            new_student_email=pref.new_student_email,
            class_deadline_email=pref.class_deadline_email,
            settlement_email=pref.settlement_email,
            api_cost_alert_email=pref.api_cost_alert_email,
            system_notice=pref.system_notice,
            marketing_opt_in=pref.marketing_opt_in,
        )
    else:
        # defaults (matches DB server_defaults)
        notifications = NotificationSettings()

    # ── 4. pricing ──
    month_start = date.today().replace(day=1)
    api_cost: Decimal = db.execute(
        select(func.coalesce(func.sum(UsageEvent.total_cost_usd), 0))
        .where(
            UsageEvent.partner_id == partner.org_id,
            _seoul_date_expr(UsageEvent.occurred_at) >= month_start,
        )
    ).scalar_one()

    api_cost = Decimal(str(api_cost))
    platform_fee = (api_cost * PLATFORM_FEE_RATE).quantize(Decimal("0.0001"))

    pricing = PricingInfo(
        platform_fee_rate=PLATFORM_FEE_RATE,
        current_month_api_cost=api_cost,
        current_month_platform_fee=platform_fee,
        current_month_total=api_cost + platform_fee,
    )

    return PartnerSettingsResponse(
        profile=profile,
        ai_models=ai_models,
        notifications=notifications,
        pricing=pricing,
    )
