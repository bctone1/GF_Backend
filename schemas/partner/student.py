# schemas/partner/student.py
from __future__ import annotations
from typing import Optional
from decimal import Decimal
from datetime import datetime
from pydantic import EmailStr
from schemas.base import ORMBase


# ========== partner.students ==========
class StudentCreate(ORMBase):
    partner_id: int
    full_name: str
    email: Optional[EmailStr] = None
    status: Optional[str] = None            # default at DB: 'active'
    primary_contact: Optional[str] = None
    notes: Optional[str] = None


class StudentUpdate(ORMBase):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None
    primary_contact: Optional[str] = None
    notes: Optional[str] = None


class StudentResponse(ORMBase):
    id: int
    partner_id: int
    full_name: str
    email: Optional[EmailStr] = None
    status: str
    joined_at: datetime
    primary_contact: Optional[str] = None
    notes: Optional[str] = None


# ========== partner.enrollments ==========
class EnrollmentCreate(ORMBase):
    project_id: int
    student_id: int
    status: Optional[str] = None            # default at DB: 'active'
    enrolled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: Optional[Decimal] = None  # DB default 0


class EnrollmentUpdate(ORMBase):
    status: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: Optional[Decimal] = None


class EnrollmentResponse(ORMBase):
    id: int
    project_id: int
    student_id: int
    status: str
    enrolled_at: datetime
    completed_at: Optional[datetime] = None
    progress_percent: Decimal
