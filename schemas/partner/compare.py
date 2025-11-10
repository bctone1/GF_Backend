# schemas/partner/compare.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, List

from pydantic import ConfigDict

from schemas.base import ORMBase, MoneyBase, Page
from schemas.enums import ComparisonRunStatus, ComparisonItemStatus


# ==============================
# comparison_runs
# ==============================
class ComparisonRunCreate(ORMBase):
    student_id: Optional[int] = None
    initiated_by: Optional[int] = None
    status: Optional[ComparisonRunStatus] = None  # DB default 'running'
    notes: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    # started_at/ completed_at 는 서버 측에서 채움


class ComparisonRunUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    student_id: Optional[int] = None
    initiated_by: Optional[int] = None
    status: Optional[ComparisonRunStatus] = None
    notes: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    completed_at: Optional[datetime] = None


class ComparisonRunResponse(ORMBase):
    id: int
    student_id: Optional[int] = None
    initiated_by: Optional[int] = None
    status: ComparisonRunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    # 선택: 포함 반환용
    items: Optional[List["ComparisonRunItemResponse"]] = None  # noqa: F821


ComparisonRunPage = Page[ComparisonRunResponse]


# ==============================
# comparison_run_items
class ComparisonRunItemCreate(ORMBase):
    run_id: int
    model_name: str
    prompt_template_version_id: Optional[int] = None
    status: Optional[ComparisonItemStatus] = None  # DB default 'pending'
    total_tokens: Optional[int] = None
    average_latency_ms: Optional[int] = None
    total_cost: Optional[Decimal] = None


class ComparisonRunItemUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    model_name: Optional[str] = None
    prompt_template_version_id: Optional[int] = None
    status: Optional[ComparisonItemStatus] = None
    total_tokens: Optional[int] = None
    average_latency_ms: Optional[int] = None
    total_cost: Optional[Decimal] = None


class ComparisonRunItemResponse(MoneyBase):
    id: int
    run_id: int
    model_name: str
    prompt_template_version_id: Optional[int] = None
    status: ComparisonItemStatus
    total_tokens: Optional[int] = None
    average_latency_ms: Optional[int] = None
    total_cost: Optional[Decimal] = None


ComparisonRunItemPage = Page[ComparisonRunItemResponse]
