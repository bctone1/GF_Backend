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
    """
    [사용자 생성용]
    - owner_id, progress, practice_hours 같은 값은 서버에서 채운다.
    - 현재 컨셉: 특정 class 안의 개인 프로젝트(폴더)
    """
    model_config = ConfigDict(from_attributes=False)

    class_id: int               # 어떤 class 안의 프로젝트인지 (필수)
    name: str
    description: Optional[str] = None
    # project_type/status 는 서버에서 기본값('personal', 'active') 사용


class UserProjectUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    class_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    progress_percent: Optional[Decimal] = None
    practice_hours: Optional[Decimal] = None
    conversation_count: Optional[int] = None
    last_activity_at: Optional[datetime] = None


class UserProjectResponse(ORMBase):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: str},
    )

    project_id: int
    owner_id: int
    class_id: int

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
    conversation_count: int = 0

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
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: str},
    )

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


# =========================================================
# View DTO: “프로젝트 상세 화면에서, ‘세션 카드 목록’을 그리기 위해
# 프론트에 넘겨줄 전용 응답 모델”
#   - 카드 목록용: 제목, 내용 일부, 대표 모델 태그, 마지막 활동 시각
# =========================================================
class ProjectSessionSummaryResponse(ORMBase):
    """
    특정 project 안에 속한 practice_session 카드용 요약 정보.
    - session_id: 세션 상세/대화방으로 들어갈 때 사용
    - last_message_preview: 마지막 메시지 일부 (백엔드에서 잘라서 전달)
    - primary_model_name: 내부 모델 이름 (예: gpt-4o, claude-3-5-haiku)
    - primary_model_label: UI에 찍을 짧은 이름 (예: GPT-4, Claude)
    """
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    project_id: int
    class_id: Optional[int] = None

    title: str
    last_message_preview: str

    primary_model_name: str
    primary_model_label: Optional[str] = None

    last_activity_at: datetime
