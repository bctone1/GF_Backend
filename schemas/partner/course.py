# schemas/partner/course.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List, Literal
from pydantic import ConfigDict

from schemas.base import ORMBase, Page
from schemas.enums import CourseStatus, ClassStatus  # 과정/분반 상태


# ==============================
# courses
# ==============================
class CourseCreate(ORMBase):
    partner_id: int
    title: str
    code: str
    status: Optional[CourseStatus] = None  # DB default 'draft'
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class CourseUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    title: Optional[str] = None
    code: Optional[str] = None
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class CourseResponse(ORMBase):
    id: int
    partner_id: int
    title: str
    code: str
    status: CourseStatus
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


CoursePage = Page[CourseResponse]


# ==============================
# classes
# ==============================
class ClassCreate(ORMBase):
    course_id: int
    name: str
    section_code: Optional[str] = None
    status: Optional[ClassStatus] = None  # DB default 'planned'
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None  # DB default 'UTC'
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None  # DB default false


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


class ClassResponse(ORMBase):
    id: int
    course_id: int
    name: str
    section_code: Optional[str] = None
    status: ClassStatus
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: str
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: bool
    created_at: datetime
    updated_at: datetime


ClassPage = Page[ClassResponse]


# ==============================
# class_instructors
# ==============================
# enums에 InstructorRole을 추가할 수도 있으나, 즉시 사용 가능하도록 Literal 사용
InstructorRole = Literal["lead", "assistant"]

class ClassInstructorCreate(ORMBase):
    class_id: int
    partner_user_id: int
    role: Optional[InstructorRole] = None  # DB default 'assistant'


class ClassInstructorUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    role: Optional[InstructorRole] = None


class ClassInstructorResponse(ORMBase):
    id: int
    class_id: int
    partner_user_id: int
    role: InstructorRole
    created_at: datetime


ClassInstructorPage = Page[ClassInstructorResponse]


# ==============================
# invite_codes
# ==============================
class InviteCodeCreate(ORMBase):
    class_id: int
    code: str
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None  # NULL = unlimited
    is_active: Optional[bool] = None  # DB default true
    created_by: Optional[int] = None


class InviteCodeUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    # 일반적으로 code는 변경하지 않지만 필요 시 허용
    code: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None
    created_by: Optional[int] = None


class InviteCodeResponse(ORMBase):
    id: int
    class_id: int
    code: str
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    uses_count: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime


InviteCodePage = Page[InviteCodeResponse]
