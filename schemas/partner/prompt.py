# schemas/partner/prompt.py
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from schemas.base import ORMBase


# ========= partner.prompt_templates =========
class PromptTemplateCreate(ORMBase):
    partner_id: Optional[int] = None         # 전역 템플릿 허용
    name: str
    description: Optional[str] = None
    scope: str = "partner"                   # 'partner' 등
    created_by: Optional[int] = None
    is_archived: bool = False


class PromptTemplateUpdate(ORMBase):
    partner_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    created_by: Optional[int] = None
    is_archived: Optional[bool] = None


class PromptTemplateResponse(ORMBase):
    id: int
    partner_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    scope: str
    created_by: Optional[int] = None
    is_archived: bool
    created_at: datetime


# ========= partner.prompt_template_versions =========
class PromptTemplateVersionCreate(ORMBase):
    template_id: int
    version: int
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None


class PromptTemplateVersionUpdate(ORMBase):
    version: Optional[int] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None


class PromptTemplateVersionResponse(ORMBase):
    id: int
    template_id: int
    version: int
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None
    created_at: datetime


# ========= partner.prompt_bindings =========
class PromptBindingCreate(ORMBase):
    template_version_id: int
    scope_type: str                         # 'project' | 'global'
    scope_id: Optional[int] = None          # global이면 None
    is_active: bool = True


class PromptBindingUpdate(ORMBase):
    template_version_id: Optional[int] = None
    scope_type: Optional[str] = None
    scope_id: Optional[int] = None
    is_active: Optional[bool] = None


class PromptBindingResponse(ORMBase):
    id: int
    template_version_id: int
    scope_type: str
    scope_id: Optional[int] = None
    is_active: bool
    created_at: datetime
