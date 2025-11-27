# schemas/partner/partner_core.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from schemas.base import Page


# ==============================
# Org (partner.org)
# ==============================
class OrgBase(BaseModel):
    name: str
    code: str
    status: str = "active"   # active|inactive|suspended
    timezone: str = "UTC"


class OrgCreate(OrgBase):
    """
    Org 생성 시 사용하는 스키마.
    created_by, created_at 등은 서버에서 채움.
    """
    pass


class OrgUpdate(BaseModel):
    """
    Org 수정 시 사용하는 스키마.
    부분 업데이트 허용.
    """
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[str] = None
    timezone: Optional[str] = None


class OrgResponse(OrgBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrgPage(Page[OrgResponse]):
    model_config = ConfigDict(from_attributes=True)


# ==============================
# Partner (partner.partners)
# Org(기관)에 속한 파트너(강사/어시스턴트)
# ==============================

class PartnerBase(BaseModel):
    org_id: int
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str = "partner"   # partner | assistant
    is_active: bool = True


class PartnerCreate(PartnerBase):
    """
    파트너(강사/어시스턴트) 생성용.
    user_id는 필요한 경우에만 받는다.
    """
    user_id: Optional[int] = None


class PartnerUpdate(BaseModel):
    """
    파트너(강사/어시스턴트) 수정용.
    """
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PartnerResponse(PartnerBase):
    id: int
    user_id: Optional[int] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartnerPage(Page[PartnerResponse]):
    model_config = ConfigDict(from_attributes=True)
