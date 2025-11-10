# schemas/partner/catalog.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import ConfigDict

from schemas.base import ORMBase, Page


# ==============================
# provider_credentials
# ==============================
class ProviderCredentialCreate(ORMBase):
    partner_id: int
    provider: str
    credential_label: Optional[str] = None
    api_key_encrypted: str
    is_active: Optional[bool] = None  # DB default true


class ProviderCredentialUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    credential_label: Optional[str] = None
    api_key_encrypted: Optional[str] = None
    is_active: Optional[bool] = None
    # last_validated_at는 보통 시스템이 갱신하므로 제외해도 됨. 필요 시 Optional[datetime]


class ProviderCredentialResponse(ORMBase):
    id: int
    partner_id: int
    provider: str
    credential_label: Optional[str] = None
    is_active: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    # 보안상 api_key_encrypted는 응답에서 제외


ProviderCredentialPage = Page[ProviderCredentialResponse]


# ==============================
# model_catalog
# ==============================
class ModelCatalogCreate(ORMBase):
    provider: str
    model_name: str
    modality: Optional[str] = None  # DB default 'chat'
    supports_parallel: Optional[bool] = None  # DB default false
    default_pricing: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None  # DB default true


class ModelCatalogUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    provider: Optional[str] = None
    model_name: Optional[str] = None
    modality: Optional[str] = None
    supports_parallel: Optional[bool] = None
    default_pricing: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class ModelCatalogResponse(ORMBase):
    id: int
    provider: str
    model_name: str
    modality: str
    supports_parallel: bool
    default_pricing: Optional[dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


ModelCatalogPage = Page[ModelCatalogResponse]


# ==============================
# org_llm_settings
# ==============================
class OrgLlmSettingCreate(ORMBase):
    partner_id: int
    default_chat_model: str
    enable_parallel_mode: Optional[bool] = None  # DB default false
    daily_message_limit: Optional[int] = None
    token_alert_threshold: Optional[int] = None
    provider_credential_id: Optional[int] = None
    updated_by: Optional[int] = None  # 시스템에서 채움 가능


class OrgLlmSettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    default_chat_model: Optional[str] = None
    enable_parallel_mode: Optional[bool] = None
    daily_message_limit: Optional[int] = None
    token_alert_threshold: Optional[int] = None
    provider_credential_id: Optional[int] = None
    updated_by: Optional[int] = None


class OrgLlmSettingResponse(ORMBase):
    id: int
    partner_id: int
    default_chat_model: str
    enable_parallel_mode: bool
    daily_message_limit: Optional[int] = None
    token_alert_threshold: Optional[int] = None
    provider_credential_id: Optional[int] = None
    updated_by: Optional[int] = None
    updated_at: datetime


OrgLlmSettingPage = Page[OrgLlmSettingResponse]
