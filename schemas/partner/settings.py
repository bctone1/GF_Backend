# schemas/partner/settings.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from pydantic import ConfigDict, Field
from schemas.base import ORMBase


# ─────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────
class ProfileSettings(ORMBase):
    partner_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    org_name: str
    role: str


class ProfileUpdateRequest(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    full_name: Optional[str] = None
    phone: Optional[str] = None


# ─────────────────────────────────────────────
# AI Model Settings
# ─────────────────────────────────────────────
class ModelSettingItem(ORMBase):
    model_id: int
    provider: str
    model_name: str
    modality: str
    is_active: bool
    default_pricing: Optional[dict] = None


class AiModelSettings(ORMBase):
    default_chat_model: Optional[str] = None
    enable_parallel_mode: bool = False
    daily_message_limit: Optional[int] = None
    token_alert_threshold: Optional[int] = None
    available_models: List[ModelSettingItem] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Notification Settings
# ─────────────────────────────────────────────
class NotificationSettings(ORMBase):
    new_student_email: bool = True
    class_deadline_email: bool = True
    settlement_email: bool = True
    api_cost_alert_email: bool = True
    system_notice: bool = True
    marketing_opt_in: bool = False


class NotificationUpdateRequest(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    new_student_email: Optional[bool] = None
    class_deadline_email: Optional[bool] = None
    settlement_email: Optional[bool] = None
    api_cost_alert_email: Optional[bool] = None
    system_notice: Optional[bool] = None
    marketing_opt_in: Optional[bool] = None


# ─────────────────────────────────────────────
# Pricing Info
# ─────────────────────────────────────────────
class PricingInfo(ORMBase):
    model_config = ConfigDict(json_encoders={Decimal: str})

    platform_fee_rate: Decimal = Decimal("0.15")
    current_month_api_cost: Decimal = Decimal("0")
    current_month_platform_fee: Decimal = Decimal("0")
    current_month_total: Decimal = Decimal("0")


# ─────────────────────────────────────────────
# Unified Response
# ─────────────────────────────────────────────
class PartnerSettingsResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

    profile: ProfileSettings
    ai_models: AiModelSettings
    notifications: NotificationSettings
    pricing: PricingInfo
