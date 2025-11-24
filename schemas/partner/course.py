# schemas/partner/course.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, ConfigDict

from schemas.base import ORMBase, Page
from schemas.enums import CourseStatus, ClassStatus


# student 초대코드 전용
InviteTargetRole = Literal["student"]
InviteStatus = Literal["active", "expired", "disabled"]


# ==============================
# courses
# ==============================
class CourseBase(ORMBase):
    title: str
    course_key: str
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class CourseCreate(ORMBase):
    """
    org_id 는 path(`/orgs/{org_id}/courses` 등)에서 받으므로 body에는 포함 X
    """
    title: str
    course_key: str
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class CourseUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    course_key: Optional[str] = None
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class CourseResponse(CourseBase):
    id: int
    org_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================
# classes
# ==============================
class ClassBase(ORMBase):
    name: str
    section_code: Optional[str] = None
    status: Optional[ClassStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None


class ClassCreate(ORMBase):
    """
    partner_id 는 path(`/partner/{partner_id}/classes`) 등에서
    course_id 가 있다면 path(`/courses/{course_id}/classes`)나 컨텍스트에서 받음
    body에는 포함 X. 코스가 없을수도 있어서 분리해서 가는 구조로
    """
    name: str
    section_code: Optional[str] = None
    status: Optional[ClassStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None


class ClassUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    name: Optional[str] = None
    section_code: Optional[str] = None
    status: Optional[ClassStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None


class ClassResponse(ClassBase):
    id: int
    partner_id: int
    course_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================
# invite_codes
# ==============================
class InviteCodeBase(ORMBase):
    code: str
    # 항상 student 초대코드
    target_role: InviteTargetRole = "student"
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    status: Optional[InviteStatus] = None  # 없으면 DB default('active') 사용


class InviteCodeCreate(ORMBase):
    """
    partner_id, class_id, created_by 는
    path(`/partner/{partner_id}/classes/{class_id}/invites`) 등에서 결정.
    클라이언트는 code / expires_at / max_uses 정도만 보냄.
    """
    code: str
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    status: Optional[InviteStatus] = None  # 없으면 DB default('active') 사용


class InviteCodeUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    status: Optional[InviteStatus] = None  # active | expired | disabled


class InviteCodeResponse(InviteCodeBase):
    id: int
    partner_id: int
    class_id: int  # class-only, NOT NULL
    used_count: int
    created_by: Optional[int] = None
    created_at: datetime
    status: InviteStatus  # 응답에서는 항상 값 존재

    model_config = ConfigDict(from_attributes=True)


# ==============================
# Invite DTOs (endpoint 전용)
# ==============================
class InviteSendRequest(BaseModel):
    """
    이메일로 초대 링크를 보낼 때 사용하는 DTO.
    partner_id / class_id / target_role 은 path 및 서버 로직에서 결정.
    """
    email: EmailStr
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None


class InviteAssignRequest(BaseModel):
    """
    이미 생성된 코드와 이메일을 묶어 관리할 때 사용하는 DTO.
    partner_id / class_id / target_role 은 path 및 서버 로직에서 결정.
    """
    email: EmailStr
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None


class InviteResendRequest(BaseModel):
    email: EmailStr


class InviteSendResponse(BaseModel):
    invite_id: int
    code: str
    invite_url: str
    email: EmailStr
    is_existing_user: bool
    email_sent: bool


# ==============================
# pagination wrappers
# ==============================
class CoursePage(Page[CourseResponse]): ...
class ClassPage(Page[ClassResponse]): ...
class InviteCodePage(Page[InviteCodeResponse]): ...
