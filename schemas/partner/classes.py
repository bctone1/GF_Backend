# schemas/partner/classes.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional, List

from pydantic import ConfigDict, Field

from schemas.base import ORMBase, Page
from schemas.enums import CourseStatus, ClassStatus


# ==============================
# Course (과정) - Org 기준
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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseTitle(CourseBase):
    # 필요 시 id 추가해서 씀
    # id: int
    title: str


class CoursePage(Page[CourseResponse]):
    ...


# ==============================
# InviteCode (수강 초대 코드)
# ==============================
class InviteCodeResponse(ORMBase):
    id: int
    partner_id: int
    class_id: int
    code: str
    target_role: str
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    used_count: int
    status: str
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InviteCodePage(Page[InviteCodeResponse]):
    ...


# ==============================
# Class (강의실) - Partner 기준
# ==============================
class ClassBase(ORMBase):
    """
    강의실 기본 정보.
    partner_id / course_id 는 보통 path 또는 서버 측에서 주입.
    """
    name: str
    status: Optional[ClassStatus] = None
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None

    # LLM 설정 (강의실 단위)
    primary_model_id: Optional[int] = None
    allowed_model_ids: List[int] = Field(default_factory=list)

    # 예산
    budget_limit: Optional[Decimal] = None


class ClassCreate(ORMBase):
    """
    partner_id, course_id 는 보통 path(`/partners/{partner_id}/classes`)나
    쿼리/서버 컨텍스트에서 받는다고 가정.
    """
    name: str
    status: Optional[ClassStatus] = None
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None

    # body 에서 같이 받는 옵션
    course_id: Optional[int] = None

    # LLM 설정 (선택)
    primary_model_id: Optional[int] = None
    allowed_model_ids: List[int] = Field(default_factory=list)

    # 예산
    budget_limit: Optional[Decimal] = None


class ClassUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    name: Optional[str] = None
    status: Optional[ClassStatus] = None
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None
    course_id: Optional[int] = None

    # LLM 설정 (선택)
    primary_model_id: Optional[int] = None
    allowed_model_ids: Optional[List[int]] = None

    # 예산
    budget_limit: Optional[Decimal] = None


class ClassResponse(ClassBase):
    """
    DB → 응답용 스키마
    - invite_codes: 이 Class 에 연관된 초대코드 리스트
    """
    id: int
    partner_id: int
    course_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # 초대 코드 목록
    invite_codes: List[InviteCodeResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ClassPage(Page[ClassResponse]):
    ...


# ==============================
# Class Summary (강의 카드용 요약)
# ==============================
class ClassSummaryResponse(ORMBase):
    """강의 카드용 요약 — 목록에서 사용."""
    id: int
    name: str
    status: str
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    budget_limit: Optional[Decimal] = None

    # 통계
    student_count: int = 0
    conversation_count: int = 0
    total_cost: Decimal = Decimal("0")
    days_remaining: Optional[int] = None

    # 예산
    budget_used: Decimal = Decimal("0")
    budget_percent: Decimal = Decimal("0")
    budget_status: Literal["ok", "warning", "alert"] = "ok"

    # 초대코드 (첫 active 코드)
    invite_code: Optional[str] = None

    created_at: datetime


# ==============================
# Cost Estimate (비용 견적)
# ==============================
class CostEstimateRequest(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    expected_students: int = Field(..., ge=1)
    model_count: int = Field(..., ge=1)
    days: int = Field(..., ge=1)


class CostEstimateResponse(ORMBase):
    platform_fee: Decimal
    api_fee_estimate: Decimal
    total: Decimal
