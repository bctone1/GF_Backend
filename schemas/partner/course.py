# schemas/partner/course.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from pydantic import ConfigDict, Field

from schemas.base import ORMBase, Page
from schemas.enums import CourseStatus


class CourseBase(ORMBase):
    title: str
    course_key: str
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None

    # LLM 설정
    primary_model_id: Optional[int] = None
    allowed_model_ids: List[int] = Field(default_factory=list)


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

    # LLM 설정 (선택)
    primary_model_id: Optional[int] = None
    allowed_model_ids: List[int] = Field(default_factory=list)


class CourseUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    course_key: Optional[str] = None
    status: Optional[CourseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None

    primary_model_id: Optional[int] = None
    allowed_model_ids: Optional[List[int]] = None


class CourseResponse(CourseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoursePage(Page[CourseResponse]):
    ...
