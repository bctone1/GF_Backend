# schemas/partner/prompt.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal, Any, List

from pydantic import ConfigDict

from schemas.base import ORMBase, Page


# ==============================
# prompt_templates
# ==============================
TemplateScope = Literal["partner", "global"]

class PromptTemplateCreate(ORMBase):
    partner_id: Optional[int] = None  # scope='partner'면 필요, 'global'이면 None
    name: str
    description: Optional[str] = None
    scope: Optional[TemplateScope] = None  # DB default 'partner'
    created_by: Optional[int] = None
    is_archived: Optional[bool] = None  # DB default false


class PromptTemplateUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    partner_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[TemplateScope] = None
    created_by: Optional[int] = None
    is_archived: Optional[bool] = None


class PromptTemplateResponse(ORMBase):
    id: int
    partner_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    scope: TemplateScope
    created_by: Optional[int] = None
    is_archived: bool
    created_at: datetime
    # 선택: 버전 동시 반환 시
    versions: Optional[List["PromptTemplateVersionResponse"]] = None  # noqa: F821


PromptTemplatePage = Page[PromptTemplateResponse]


# ==============================
# prompt_template_versions
# ==============================
class PromptTemplateVersionCreate(ORMBase):
    template_id: int
    version: int
    content: str
    meta: Optional[dict[str, Any]] = None
    created_by: Optional[int] = None


class PromptTemplateVersionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    version: Optional[int] = None
    content: Optional[str] = None
    meta: Optional[dict[str, Any]] = None
    created_by: Optional[int] = None


class PromptTemplateVersionResponse(ORMBase):
    id: int
    template_id: int
    version: int
    content: str
    meta: Optional[dict[str, Any]] = None
    created_by: Optional[int] = None
    created_at: datetime


PromptTemplateVersionPage = Page[PromptTemplateVersionResponse]


# ==============================
# prompt_bindings
# ==============================
BindingScope = Literal["class", "global"]

class PromptBindingCreate(ORMBase):
    template_version_id: int
    scope_type: BindingScope  # 'class'|'global'
    scope_id: Optional[int] = None            # scope_type='class'면 필요
    is_active: Optional[bool] = None          # DB default true


class PromptBindingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    template_version_id: Optional[int] = None
    scope_type: Optional[BindingScope] = None
    scope_id: Optional[int] = None
    is_active: Optional[bool] = None


class PromptBindingResponse(ORMBase):
    id: int
    template_version_id: int
    scope_type: BindingScope
    scope_id: Optional[int] = None
    is_active: bool
    created_at: datetime


PromptBindingPage = Page[PromptBindingResponse]
