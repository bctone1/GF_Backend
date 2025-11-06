# schemas/links/links.py
from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from schemas.base import ORMBase

# ----- enums: 플랫폼 공통 enums를 우선 사용 -----
try:
    # 권장: 공통 enum 재사용
    from schemas.enums import Status  # e.g. active|inactive|suspended|draft
except Exception:
    # 임시 폴백(필요 시 삭제)
    from enum import Enum
    class Status(str, Enum):
        active = "active"
        inactive = "inactive"
        suspended = "suspended"
        draft = "draft"

try:
    # 선택: 조직 내 사용자 역할이 enums에 있다면 사용
    from schemas.enums import OrgRole  # e.g. owner|admin|manager|member|student|instructor
except Exception:
    # 임시 폴백(필요 시 삭제)
    from enum import Enum
    class OrgRole(str, Enum):
        owner = "owner"
        admin = "admin"
        manager = "manager"
        member = "member"
        student = "student"
        instructor = "instructor"


# =========================================================
# partner_org_link  (supervisor.organizations ↔ partner.partners)
# =========================================================

class PartnerOrgLinkCreate(ORMBase):
    """
    교차 링크 생성 스키마.
    - supervisor.organizations.organization_id ↔ partner.partners.partner_id
    """
    model_config = ConfigDict(from_attributes=False)

    organization_id: int  # supervisor.organizations PK
    partner_id: int       # partner.partners PK
    is_primary: bool = False
    notes: Optional[str] = None


class PartnerOrgLinkUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    is_primary: Optional[bool] = None
    status: Optional[Status] = None
    notes: Optional[str] = None


class PartnerOrgLinkResponse(ORMBase):
    """
    읽기 응답 스키마. DB의 from_attributes 매핑 활성화.
    """
    model_config = ConfigDict(from_attributes=True)

    link_id: int
    organization_id: int
    partner_id: int
    status: Status
    is_primary: bool
    notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime


# =========================================================
# org_user_link  (supervisor.organizations ↔ user.users)
# =========================================================

class OrgUserLinkCreate(ORMBase):
    """
    조직-사용자 연결. 조직 멤버십/소속/역할을 명시.
    """
    model_config = ConfigDict(from_attributes=False)

    organization_id: int  # supervisor.organizations PK
    user_id: int          # user.users PK
    role: OrgRole = OrgRole.member
    status: Status = Status.active
    notes: Optional[str] = None


class OrgUserLinkUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    role: Optional[OrgRole] = None
    status: Optional[Status] = None
    notes: Optional[str] = None
    # 탈퇴/비활성화 처리 시 타임스탬프는 서버에서 채움(예: left_at)


class OrgUserLinkResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    link_id: int
    organization_id: int
    user_id: int
    role: OrgRole
    status: Status
    notes: Optional[str] = None

    joined_at: Optional[datetime] = None  # 서버 채움(생성 시 now)
    left_at: Optional[datetime] = None    # 비활성/탈퇴 시 서버 채움

    created_at: datetime
    updated_at: datetime
