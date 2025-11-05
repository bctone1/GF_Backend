# schemas/partner/catalog.py
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from schemas.base import ORMBase


# ========= partner.provider_credentials =========
class ProviderCredentialCreate(ORMBase):
    partner_id: int
    provider: str
    credential_label: Optional[str] = None
    api_key_encrypted: str
    is_active: bool = True
    last_validated_at: Optional[datetime] = None


class ProviderCredentialUpdate(ORMBase):
    provider: Optional[str] = None
    credential_label: Optional[str] = None
    api_key_encrypted: Optional[str] = None
    is_active: Optional[bool] = None
    last_validated_at: Optional[datetime] = None


class ProviderCredentialResponse(ORMBase):
    id: int
    partner_id: int
    provider: str
    credential_label: Optional[str] = None
    api_key_encrypted: str
    is_active: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime


# ========= partner.model_catalog =========
class ModelCatalogCreate(ORMBase):
    provider: str
    model_name: str
    modality: str = "chat"                 # chat | embedding | stt | image ...
    supports_parallel: bool = False
    default_pricing: Optional[Dict[str, Any]] = None
    is_active: bool = True


class ModelCatalogUpdate(ORMBase):
    provider: Optional[str] = None
    model_name: Optional[str] = None
    modality: Optional[str] = None
    supports_parallel: Optional[bool] = None
    default_pricing: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ModelCatalogResponse(ORMBase):
    id: int
    provider: str
    model_name: str
    modality: str
    supports_parallel: bool
    default_pricing: Optional[Dict[str, Any]] = None
    is_active: bool


# ========= partner.org_llm_settings =========
class OrgLlmSettingCreate(ORMBase):
    partner_id: int
    default_chat_model: str
    enable_parallel_mode: bool = False
    daily_message_limit: Optional[int] = None
    token_alert_threshold: Optional[int] = None
    provider_credential_id: Optional[int] = None
    updated_by: Optional[int] = None


class OrgLlmSettingUpdate(ORMBase):
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
