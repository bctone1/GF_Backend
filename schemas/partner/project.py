# schemas/partner/project.py
from __future__ import annotations
from typing import Optional
from decimal import Decimal
from datetime import datetime, date
from schemas.base import ORMBase, MoneyBase


# ========== partner.projects ==========
class ProjectCreate(MoneyBase):
    partner_id: int
    name: str
    status: str = "planning"
    contract_amount: Decimal = Decimal("0")
    expected_student_count: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    created_by: Optional[int] = None


class ProjectUpdate(MoneyBase):
    name: Optional[str] = None
    status: Optional[str] = None
    contract_amount: Optional[Decimal] = None
    expected_student_count: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    created_by: Optional[int] = None


class ProjectResponse(MoneyBase):
    id: int
    partner_id: int
    name: str
    status: str
    contract_amount: Decimal
    expected_student_count: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ========== partner.project_settings ==========
class ProjectSettingCreate(ORMBase):
    project_id: int
    auto_approve_students: bool = False
    allow_self_registration: bool = True
    # Represent Postgres INTERVAL as ISO-8601 duration string or seconds string. Keep as str.
    default_project_duration: Optional[str] = None
    auto_prune_inactive: bool = False
    inactive_days_threshold: Optional[int] = 60
    updated_by: Optional[int] = None


class ProjectSettingUpdate(ORMBase):
    auto_approve_students: Optional[bool] = None
    allow_self_registration: Optional[bool] = None
    default_project_duration: Optional[str] = None
    auto_prune_inactive: Optional[bool] = None
    inactive_days_threshold: Optional[int] = None
    updated_by: Optional[int] = None


class ProjectSettingResponse(ORMBase):
    project_id: int
    auto_approve_students: bool
    allow_self_registration: bool
    default_project_duration: Optional[str] = None
    auto_prune_inactive: bool
    inactive_days_threshold: Optional[int] = None
    updated_by: Optional[int] = None
    updated_at: datetime


# ========== partner.project_staff ==========
class ProjectStaffCreate(ORMBase):
    project_id: int
    partner_user_id: int
    role: str
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None


class ProjectStaffUpdate(ORMBase):
    partner_user_id: Optional[int] = None
    role: Optional[str] = None
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None


class ProjectStaffResponse(ORMBase):
    id: int
    project_id: int
    partner_user_id: int
    role: str
    invited_at: datetime
    joined_at: Optional[datetime] = None
