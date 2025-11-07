# schemas/partner/notify.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import ConfigDict

from schemas.base import ORMBase, Page
from schemas.enums import EmailSubscriptionType, MfaMethod


# ==============================
# notification_preferences
# ==============================
class NotificationPreferenceCreate(ORMBase):
    partner_user_id: int
    new_student_email: Optional[bool] = None          # DB default true
    class_deadline_email: Optional[bool] = None       # DB default true
    settlement_email: Optional[bool] = None           # DB default true
    api_cost_alert_email: Optional[bool] = None       # DB default true
    system_notice: Optional[bool] = None              # DB default true
    marketing_opt_in: Optional[bool] = None           # DB default false


class NotificationPreferenceUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    new_student_email: Optional[bool] = None
    class_deadline_email: Optional[bool] = None
    settlement_email: Optional[bool] = None
    api_cost_alert_email: Optional[bool] = None
    system_notice: Optional[bool] = None
    marketing_opt_in: Optional[bool] = None


class NotificationPreferenceResponse(ORMBase):
    id: int
    partner_user_id: int
    new_student_email: bool
    class_deadline_email: bool
    settlement_email: bool
    api_cost_alert_email: bool
    system_notice: bool
    marketing_opt_in: bool
    updated_at: datetime


NotificationPreferencePage = Page[NotificationPreferenceResponse]


# ==============================
# email_subscriptions
# ==============================
class EmailSubscriptionCreate(ORMBase):
    partner_user_id: int
    subscription_type: EmailSubscriptionType  # 'weekly_digest'|'alerts'|'marketing'
    is_subscribed: Optional[bool] = None      # DB default true


class EmailSubscriptionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    subscription_type: Optional[EmailSubscriptionType] = None
    is_subscribed: Optional[bool] = None


class EmailSubscriptionResponse(ORMBase):
    id: int
    partner_user_id: int
    subscription_type: EmailSubscriptionType
    is_subscribed: bool
    updated_at: datetime


EmailSubscriptionPage = Page[EmailSubscriptionResponse]


# ==============================
# mfa_settings
# ==============================
class MfaSettingCreate(ORMBase):
    partner_user_id: int
    is_enabled: Optional[bool] = None          # DB default false
    method: Optional[MfaMethod] = None         # 'totp'|'sms'|'email'
    # secret_encrypted는 입력은 허용하되, 응답에는 포함하지 않음
    secret_encrypted: Optional[str] = None


class MfaSettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    is_enabled: Optional[bool] = None
    method: Optional[MfaMethod] = None
    secret_encrypted: Optional[str] = None


class MfaSettingResponse(ORMBase):
    partner_user_id: int
    is_enabled: bool
    method: Optional[MfaMethod] = None
    last_enabled_at: Optional[datetime] = None
    updated_at: datetime
    # secret_encrypted 제외


MfaSettingPage = Page[MfaSettingResponse]


# ==============================
# login_activity (append-only)
# ==============================
LoginStatus = Literal["success", "failed"]

class LoginActivityCreate(ORMBase):
    partner_user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: Optional[LoginStatus] = None       # DB default 'success'
    login_at: Optional[datetime] = None        # 서버에서 채움 권장


class LoginActivityResponse(ORMBase):
    login_at: datetime
    id: int
    partner_user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: LoginStatus


LoginActivityPage = Page[LoginActivityResponse]
