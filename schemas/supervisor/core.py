# schemas/supervisor/core.py
from __future__ import annotations

from typing import Any, Optional, Literal
from decimal import Decimal
from datetime import datetime, date

from pydantic import BaseModel, EmailStr, ConfigDict, Field
from schemas.base import ORMBase, MoneyBase


# =========================
# Supervisor Users
# =========================
class SupervisorUserCreate(ORMBase):
    organization_id: int
    email: EmailStr
    name: str
    role: str
    status: str = "active"
    last_active_at: Optional[datetime] = None
    session_avg_duration: Optional[int] = None
    total_usage: int = 0


class SupervisorUserUpdate(ORMBase):
    organization_id: Optional[int] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    last_active_at: Optional[datetime] = None
    session_avg_duration: Optional[int] = None
    total_usage: Optional[int] = None


class SupervisorUserResponse(ORMBase):
    user_id: int
    organization_id: int
    email: EmailStr
    name: str
    role: str
    status: str
    last_active_at: Optional[datetime] = None
    signup_at: datetime
    session_avg_duration: Optional[int] = None
    total_usage: int
    created_at: datetime
    updated_at: datetime

# =========================
# Partner Promotion Requests
# =========================
PromotionStatus = Literal["pending", "approved", "rejected", "cancelled"]

class PartnerPromotionRequestCreate(ORMBase):
    """
    유저가 강사/파트너 승격 신청을 생성할 때 사용하는 입력 스키마
    - user_id, requested_at, status 등은 서버에서 채움
    """

    # 요청폼에서 입력
    name: str
    email: str
    org_name: str
    edu_category: Optional[str] = None
    # 기본 파트너 역할
    target_role: str = "partner_admin"


class PartnerPromotionRequestUpdate(ORMBase):
    """
    supervisor 쪽에서 승인/거절 처리 시 사용하는 스키마
    """

    status: Optional[PromotionStatus] = None
    decided_at: Optional[datetime] = None
    partner_id: Optional[int] = None
    partner_user_id: Optional[int] = None
    target_role: Optional[str] = None

    # 필요 시 신청 정보도 수정 가능하도록 옵션 필드로 둠
    name: Optional[str] = None
    email: Optional[str] = None
    org_name: Optional[str] = None
    edu_category: Optional[str] = None


class PartnerPromotionRequestResponse(ORMBase):
    """
    목록/단건 조회 응답 스키마
    models.supervisor.core.PartnerPromotionRequest와 1:1 매핑
    """

    request_id: int
    user_id: int

    # 요청폼에서 입력된 값
    name: str
    email: str
    org_name: str
    edu_category: Optional[str] = None
    target_role: str = "partner_admin"

    status: PromotionStatus
    requested_at: datetime
    decided_at: Optional[datetime] = None

    # 승인 후 실제 연결된 partner / partner_user
    partner_id: Optional[int] = None
    partner_user_id: Optional[int] = None


# =========================
# user_roles
# =========================
class UserRoleCreate(ORMBase):
    role_name: str
    permissions_json: dict[str, Any]


class UserRoleUpdate(ORMBase):
    role_name: Optional[str] = None
    permissions_json: Optional[dict[str, Any]] = None


class UserRoleResponse(ORMBase):
    role_id: int
    role_name: str
    permissions_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# =========================
# user_role_assignments
# =========================
class UserRoleAssignmentCreate(ORMBase):
    # SupervisorUser.user_id 를 참조
    user_id: int
    role_id: int
    assigned_by: Optional[int] = None


class UserRoleAssignmentUpdate(ORMBase):
    assigned_by: Optional[int] = None


class UserRoleAssignmentResponse(ORMBase):
    assignment_id: int
    user_id: int
    role_id: int
    assigned_at: datetime
    assigned_by: Optional[int] = None


# =========================
# sessions
# =========================
class SessionCreate(ORMBase):
    # SupervisorUser.user_id 를 참조
    user_id: int
    organization_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    device_info: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None  # INET → str


class SessionUpdate(ORMBase):
    ended_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    device_info: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None


class SessionResponse(ORMBase):
    session_id: int
    user_id: int
    organization_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    device_info: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None


# =========================
# promotions (기존: supervisor가 바로 partner 생성하는 API용 DTO)
# =========================
class PromotionRequest(BaseModel):
    model_config = ConfigDict(from_attributes=False)
    email: EmailStr
    partner_name: str
    partner_code: Optional[str] = None
    partner_user_role: Optional[str] = None  # default handled server-side


class PromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    partner_id: int
    partner_code: str
    partner_name: str
    partner_user_id: int
    user_id: int
    role: str


# =========================
# organizations
# =========================
class OrganizationCreate(MoneyBase):
    name: str
    plan_id: Optional[int] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    status: str = "active"
    joined_at: Optional[date] = None
    trial_end_at: Optional[date] = None
    mrr: Decimal = Decimal("0")
    notes: Optional[str] = None
    created_by: Optional[int] = None


class OrganizationUpdate(MoneyBase):
    name: Optional[str] = None
    plan_id: Optional[int] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    status: Optional[str] = None
    joined_at: Optional[date] = None
    trial_end_at: Optional[date] = None
    mrr: Optional[Decimal] = None
    notes: Optional[str] = None
    created_by: Optional[int] = None


class OrganizationResponse(MoneyBase):
    organization_id: int
    name: str
    plan_id: Optional[int] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    status: str
    joined_at: date
    trial_end_at: Optional[date] = None
    mrr: Decimal
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# =========================
# plans
# =========================
class PlanCreate(MoneyBase):
    plan_name: str
    billing_cycle: str = "monthly"
    price_mrr: Decimal = Decimal("0")
    price_arr: Decimal = Decimal("0")
    features_json: Optional[dict[str, Any]] = None
    max_users: Optional[int] = None
    is_active: bool = True


class PlanUpdate(MoneyBase):
    plan_name: Optional[str] = None
    billing_cycle: Optional[str] = None
    price_mrr: Optional[Decimal] = None
    price_arr: Optional[Decimal] = None
    features_json: Optional[dict[str, Any]] = None
    max_users: Optional[int] = None
    is_active: Optional[bool] = None


class PlanResponse(MoneyBase):
    plan_id: int
    plan_name: str
    billing_cycle: str
    price_mrr: Decimal
    price_arr: Decimal
    features_json: Optional[dict[str, Any]] = None
    max_users: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
