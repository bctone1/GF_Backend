# schemas/partner/course.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List
from pydantic import ConfigDict
from decimal import Decimal

from schemas.base import ORMBase, Page
from schemas.enums import CourseStatus, ClassStatus


# ==============================
# courses
# ==============================
class CourseBase(ORMBase):
    title: str
    code: str
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class CourseCreate(CourseBase):
    partner_id: int


class CourseUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    title: Optional[str] = None
    code: Optional[str] = None
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class CourseResponse(CourseBase):
    id: int
    partner_id: int
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


class ClassCreate(ClassBase):
    course_id: int


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
    course_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================
# class_instructors
# ==============================
class ClassInstructorBase(ORMBase):
    class_id: int
    partner_user_id: int
    role: str  # lead | assistant


class ClassInstructorCreate(ClassInstructorBase):
    pass


class ClassInstructorUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    role: Optional[str] = None


class ClassInstructorResponse(ClassInstructorBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================
# invite_codes
# ==============================
class InviteCodeBase(ORMBase):
    code: str
    target_role: str  # instructor | student
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    used_count: Optional[int] = None
    status: Optional[str] = None


class InviteCodeCreate(InviteCodeBase):
    partner_id: int
    class_id: Optional[int] = None
    created_by: Optional[int] = None


class InviteCodeUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    target_role: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class InviteCodeResponse(InviteCodeBase):
    id: int
    partner_id: int
    class_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================
# pagination wrappers
# ==============================
class CoursePage(Page[CourseResponse]): ...
class ClassPage(Page[ClassResponse]): ...
class InviteCodePage(Page[InviteCodeResponse]): ...
