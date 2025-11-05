# schemas/supervisor/core.py
from __future__ import annotations
from typing import Any, Optional
from decimal import Decimal
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, ConfigDict
from schemas.base import ORMBase, MoneyBase


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


# =========================
# organizations
# =========================
class OrganizationCreate(MoneyBase):
    name: str
    plan_id: Optional[int] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    status: str = "active"  # 'active' | 'trial' | 'suspended'
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
# users
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
    user_id: int
    role_id: int
    assigned_by: Optional[int] = None


class UserRoleAssignmentUpdate(ORMBase):
    # 일반적으로 수정할 필드는 거의 없음. assigned_by 정도만 허용.
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
    user_id: int
    organization_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    device_info: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None  # INET → str, 서버단 검증


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
