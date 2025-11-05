# schemas/user/project.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import ConfigDict, Field
from schemas.base import ORMBase


# =========================================================
# user.projects
# =========================================================
class UserProjectCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    owner_id: int
    name: str
    description: Optional[str] = None
    project_type: Optional[str] = None          # server default 'personal'
    status: Optional[str] = None                # server default 'active'
    progress_percent: Optional[Decimal] = None  # server default 0
    practice_hours: Optional[Decimal] = None    # server default 0
    conversation_count: Optional[int] = None    # server default 0
    last_activity_at: Optional[datetime] = None


class UserProjectUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    progress_percent: Optional[Decimal] = None
    practice_hours: Optional[Decimal] = None
    conversation_count: Optional[int] = None
    last_activity_at: Optional[datetime] = None


class UserProjectResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})
    project_id: int
    owner_id: int
    name: str
    description: Optional[str] = None
    project_type: str
    status: str
    progress_percent: Decimal
    practice_hours: Decimal
    conversation_count: int
    last_activity_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# =========================================================
# user.project_members
# =========================================================
class ProjectMemberCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    project_id: int
    user_id: int
    role: Optional[str] = None     # server default 'member'
    status: Optional[str] = None   # server default 'active'
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None


class ProjectMemberUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    role: Optional[str] = None
    status: Optional[str] = None
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None


class ProjectMemberResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    project_member_id: int
    project_id: int
    user_id: int
    role: str
    status: str
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None


# =========================================================
# user.project_tags
# =========================================================
class ProjectTagCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    name: str
    color: Optional[str] = None


class ProjectTagUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    name: Optional[str] = None
    color: Optional[str] = None


class ProjectTagResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    tag_id: int
    name: str
    color: Optional[str] = None
    created_at: datetime


# =========================================================
# user.project_tag_assignments
# =========================================================
class ProjectTagAssignmentCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    project_id: int
    tag_id: int


class ProjectTagAssignmentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    # usually immutable; placeholder for future fields
    pass


class ProjectTagAssignmentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    assignment_id: int
    project_id: int
    tag_id: int


# =========================================================
# user.project_metrics
# =========================================================
class ProjectMetricCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    project_id: int
    metric_type: str
    metric_value: Decimal
    recorded_at: Optional[datetime] = None  # server default now()


class ProjectMetricUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    metric_type: Optional[str] = None
    metric_value: Optional[Decimal] = None
    recorded_at: Optional[datetime] = None


class ProjectMetricResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})
    metric_id: int
    project_id: int
    metric_type: str
    metric_value: Decimal
    recorded_at: datetime


# =========================================================
# user.project_activity
# =========================================================
class ProjectActivityCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    project_id: int
    user_id: Optional[int] = None
    activity_type: str
    details: Optional[Dict[str, Any]] = Field(default=None)  # JSONB
    occurred_at: Optional[datetime] = None                   # server default now()


class ProjectActivityUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    activity_type: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    occurred_at: Optional[datetime] = None


class ProjectActivityResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    activity_id: int
    project_id: int
    user_id: Optional[int] = None
    activity_type: str
    details: Optional[Dict[str, Any]] = None
    occurred_at: datetime
