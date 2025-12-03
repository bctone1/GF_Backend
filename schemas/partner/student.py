# schemas/partner/student.py
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

    # AppUser 매핑용 (일반적으로는 서버/내부 로직에서 채우고, 파트너 UI에서는 안 쓰일 수도 있음)
    user_id: Optional[int] = None


class StudentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[StudentStatus] = None
    primary_contact: Optional[str] = None
    notes: Optional[str] = None

    # 기존 학생에 나중에 user_id 매핑해줄 때 사용 가능
    user_id: Optional[int] = None


class StudentResponse(ORMBase):
    id: int
    partner_id: int
    full_name: str
    email: Optional[str] = None
    status: StudentStatus
    joined_at: datetime
    primary_contact: Optional[str] = None
    notes: Optional[str] = None

    # 이 Student가 매핑된 AppUser (없을 수 있음)
    user_id: Optional[int] = None


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


class StudentClassResponse(ORMBase):
    """
    수강생 입장에서 보는 '내 강의' 카드 한 줄.
    """
    # 식별자
    enrollment_id: int
    class_id: int

    # 표시 정보
    class_title: str

    # 클래스에 연결된 LLM 모델 정보
    primary_model_id: Optional[int] = None
    allowed_model_ids: list[int] = []  # 또는 = Field(default_factory=list)

    course_title: Optional[str] = None

    org_name: Optional[str] = None
    teacher_name: Optional[str] = None

    # 클래스 일정
    class_start_at: Optional[datetime] = None
    class_end_at: Optional[datetime] = None

    # 수강 상태/기간
    enrollment_status: EnrollmentStatus
    enrolled_at: datetime
    completed_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None  # 추후 세션/활동 로그 연동 예정

StudentClassPage = Page[StudentClassResponse]
