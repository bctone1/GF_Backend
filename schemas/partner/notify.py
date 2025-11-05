# schemas/partner/notify.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from schemas.base import ORMBase


# ========= partner.notification_preferences =========
class NotificationPreferenceCreate(ORMBase):
    partner_user_id: int
    new_student_email: bool = True
    project_deadline_email: bool = True
    settlement_email: bool = True
    api_cost_alert_email: bool = True
    system_notice: bool = True
    marketing_opt_in: bool = False


class NotificationPreferenceUpdate(ORMBase):
    new_student_email: Optional[bool] = None
    project_deadline_email: Optional[bool] = None
    settlement_email: Optional[bool] = None
    api_cost_alert_email: Optional[bool] = None
    system_notice: Optional[bool] = None
    marketing_opt_in: Optional[bool] = None


class NotificationPreferenceResponse(ORMBase):
    id: int
    partner_user_id: int
    new_student_email: bool
    project_deadline_email: bool
    settlement_email: bool
    api_cost_alert_email: bool
    system_notice: bool
    marketing_opt_in: bool
    updated_at: datetime


# ========= partner.email_subscriptions =========
class EmailSubscriptionCreate(ORMBase):
    partner_user_id: int
    subscription_type: str
    is_subscribed: bool = True


class EmailSubscriptionUpdate(ORMBase):
    is_subscribed: Optional[bool] = None


class EmailSubscriptionResponse(ORMBase):
    id: int
    partner_user_id: int
    subscription_type: str
    is_subscribed: bool
    updated_at: datetime


# ========= partner.mfa_settings =========
class MfaSettingCreate(ORMBase):
    partner_user_id: int
    is_enabled: bool = False
    method: Optional[str] = None          # 'totp' | 'sms' | 'email' 등 운영에서 검증
    secret_encrypted: Optional[str] = None
    last_enabled_at: Optional[datetime] = None


class MfaSettingUpdate(ORMBase):
    is_enabled: Optional[bool] = None
    method: Optional[str] = None
    secret_encrypted: Optional[str] = None
    last_enabled_at: Optional[datetime] = None


class MfaSettingResponse(ORMBase):
    partner_user_id: int
    is_enabled: bool
    method: Optional[str] = None
    secret_encrypted: Optional[str] = None
    last_enabled_at: Optional[datetime] = None
    updated_at: datetime


# ========= partner.login_activity =========
class LoginActivityCreate(ORMBase):
    partner_user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"               # 운영에서 값 집합 검증


class LoginActivityUpdate(ORMBase):
    # 일반적으로 수정 불가. 상태 정정만 허용할 경우 사용.
    status: Optional[str] = None


class LoginActivityResponse(ORMBase):
    id: int
    partner_user_id: Optional[int] = None
    login_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
