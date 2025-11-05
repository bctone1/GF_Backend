# schemas/supervisor/settings.py
from __future__ import annotations
from typing import Any, Optional, Dict
from datetime import datetime
from pydantic import AnyUrl, EmailStr
from schemas.base import ORMBase


# ========== supervisor.platform_settings ==========
class PlatformSettingCreate(ORMBase):
    category: str
    key: str
    value: Optional[str] = None
    value_type: str
    updated_by: Optional[int] = None


class PlatformSettingUpdate(ORMBase):
    category: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    value_type: Optional[str] = None
    updated_by: Optional[int] = None


class PlatformSettingResponse(ORMBase):
    setting_id: int
    category: str
    key: str
    value: Optional[str] = None
    value_type: str
    updated_at: datetime
    updated_by: Optional[int] = None


# ========== supervisor.api_keys ==========
class ApiKeyCreate(ORMBase):
    name: str
    key_hash: str          # 원문 저장 금지
    status: str = "active" # 'active' | 'revoked' | 'disabled'
    created_by: Optional[int] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ApiKeyUpdate(ORMBase):
    name: Optional[str] = None
    status: Optional[str] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ApiKeyResponse(ORMBase):
    api_key_id: int
    name: str
    key_hash: str
    status: str
    created_at: datetime
    created_by: Optional[int] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


# ========== supervisor.rate_limits ==========
class RateLimitCreate(ORMBase):
    plan_id: Optional[int] = None
    organization_id: Optional[int] = None
    limit_type: str
    limit_value: int
    window_sec: int
    updated_by: Optional[int] = None


class RateLimitUpdate(ORMBase):
    plan_id: Optional[int] = None
    organization_id: Optional[int] = None
    limit_type: Optional[str] = None
    limit_value: Optional[int] = None
    window_sec: Optional[int] = None
    updated_by: Optional[int] = None


class RateLimitResponse(ORMBase):
    limit_id: int
    plan_id: Optional[int] = None
    organization_id: Optional[int] = None
    limit_type: str
    limit_value: int
    window_sec: int
    updated_at: datetime
    updated_by: Optional[int] = None


# ========== supervisor.webhooks ==========
class WebhookCreate(ORMBase):
    organization_id: int
    event_type: str
    target_url: AnyUrl
    status: str = "active"  # 'active' | 'disabled'
    secret: Optional[str] = None


class WebhookUpdate(ORMBase):
    event_type: Optional[str] = None
    target_url: Optional[AnyUrl] = None
    status: Optional[str] = None
    secret: Optional[str] = None


class WebhookResponse(ORMBase):
    webhook_id: int
    organization_id: int
    event_type: str
    target_url: AnyUrl
    status: str
    secret: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ========== supervisor.llm_providers ==========
class LlmProviderCreate(ORMBase):
    provider_name: str          # 'openai' 등
    api_key: str               # 암호화 저장 권장
    default_model: Optional[str] = None
    temperature: Optional[str] = None  # 필요 시 Decimal/float로 교체
    max_tokens: Optional[int] = None
    last_tested_at: Optional[datetime] = None
    status: str = "active"     # 'active' | 'inactive' | 'deprecated'


class LlmProviderUpdate(ORMBase):
    provider_name: Optional[str] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[int] = None
    last_tested_at: Optional[datetime] = None
    status: Optional[str] = None


class LlmProviderResponse(ORMBase):
    provider_id: int
    provider_name: str
    api_key: str
    default_model: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[int] = None
    last_tested_at: Optional[datetime] = None
    status: str


# ========== supervisor.email_settings ==========
class EmailSettingCreate(ORMBase):
    smtp_host: str
    smtp_port: int
    tls_enabled: bool = True

    username: Optional[str] = None
    password_encrypted: Optional[str] = None

    sender_name: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None

    template_config_json: Optional[Dict[str, Any]] = None
    last_tested_at: Optional[datetime] = None


class EmailSettingUpdate(ORMBase):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    tls_enabled: Optional[bool] = None

    username: Optional[str] = None
    password_encrypted: Optional[str] = None

    sender_name: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None

    template_config_json: Optional[Dict[str, Any]] = None
    last_tested_at: Optional[datetime] = None


class EmailSettingResponse(ORMBase):
    email_setting_id: int
    smtp_host: str
    smtp_port: int
    tls_enabled: bool

    username: Optional[str] = None
    password_encrypted: Optional[str] = None

    sender_name: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None

    template_config_json: Optional[Dict[str, Any]] = None
    last_tested_at: Optional[datetime] = None


# ========== supervisor.integrations ==========
class IntegrationCreate(ORMBase):
    type: str                      # 'slack','zendesk','github' 등
    config_json: Dict[str, Any]
    status: str = "active"         # 'active' | 'inactive'
    last_tested_at: Optional[datetime] = None


class IntegrationUpdate(ORMBase):
    type: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    last_tested_at: Optional[datetime] = None


class IntegrationResponse(ORMBase):
    integration_id: int
    type: str
    config_json: Dict[str, Any]
    status: str
    last_tested_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
