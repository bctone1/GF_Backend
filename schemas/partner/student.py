from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, EmailStr

from schemas.base import ORMBase, Page
from schemas.enums import StudentStatus, EnrollmentStatus


# ==============================
# students
# ==============================
class StudentCreate(ORMBase):
    partner_id: int
    full_name: str
    email: Optional[EmailStr] = None
    status: Optional[StudentStatus] = None            # DB default 'active'
    primary_contact: Optional[str] = None
    notes: Optional[str] = None


class StudentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[StudentStatus] = None
    primary_contact: Optional[str] = None
    notes: Optional[str] = None


class StudentResponse(ORMBase):
    id: int
    partner_id: int
    full_name: str
    email: Optional[str] = None
    status: StudentStatus
    joined_at: datetime
    primary_contact: Optional[str] = None
    notes: Optional[str] = None


StudentPage = Page[StudentResponse]


# ==============================
# enrollments
# ==============================
class EnrollmentCreate(ORMBase):
    class_id: int
    student_id: int
    invite_code_id: Optional[int] = None
    status: Optional[EnrollmentStatus] = None          # DB default 'active'
    enrolled_at: Optional[datetime] = None             # 서버 채움 가능
    completed_at: Optional[datetime] = None


class EnrollmentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    class_id: Optional[int] = None
    student_id: Optional[int] = None
    invite_code_id: Optional[int] = None
    status: Optional[EnrollmentStatus] = None
    enrolled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class EnrollmentResponse(ORMBase):
    id: int
    class_id: int
    student_id: int
    invite_code_id: Optional[int] = None
    status: EnrollmentStatus
    enrolled_at: datetime
    completed_at: Optional[datetime] = None


EnrollmentPage = Page[EnrollmentResponse]
