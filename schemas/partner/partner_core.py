# schemas/partner/partner_core.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import ConfigDict, EmailStr

from schemas.base import ORMBase, Page

# DB 제약과 동일 집합
PartnerStatus = Literal["active", "inactive", "suspended"]
PartnerUserRole = Literal["partner_admin", "instructor", "assistant"]


# ==============================
# partners
# ==============================
class PartnerCreate(ORMBase):
    name: str
    code: str
    status: Optional[PartnerStatus] = None      # DB default 'active'
    timezone: Optional[str] = None              # DB default 'UTC'


class PartnerUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[PartnerStatus] = None
    timezone: Optional[str] = None


class PartnerResponse(ORMBase):
    id: int
    name: str
    code: str
    status: PartnerStatus
    timezone: str
    created_at: datetime
    updated_at: datetime

PartnerPage = Page[PartnerResponse]


# ==============================
# partner_users
# ==============================
class PartnerUserCreate(ORMBase):
    partner_id: int
    user_id: Optional[int] = None                  # supervisor.users.user_id
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: Optional[PartnerUserRole] = None         # DB default 'partner_admin'
    is_active: Optional[bool] = None               # DB default true
    last_login_at: Optional[datetime] = None


class PartnerUserUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: Optional[int] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[PartnerUserRole] = None
    is_active: Optional[bool] = None
    last_login_at: Optional[datetime] = None


class PartnerUserResponse(ORMBase):
    id: int
    partner_id: int
    user_id: Optional[int] = None
    full_name: str
    email: str
    phone: Optional[str] = None
    role: PartnerUserRole
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


PartnerUserPage = Page[PartnerUserResponse]
