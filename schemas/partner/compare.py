# schemas/partner/compare.py
from __future__ import annotations
from typing import Optional
from decimal import Decimal
from datetime import datetime
from schemas.base import ORMBase, MoneyBase


# ========== partner.comparison_runs ==========
class ComparisonRunCreate(ORMBase):
    project_id: int
    student_id: Optional[int] = None
    initiated_by: Optional[int] = None
    status: Optional[str] = None              # DB default 'running'
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class ComparisonRunUpdate(ORMBase):
    student_id: Optional[int] = None
    initiated_by: Optional[int] = None
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class ComparisonRunResponse(ORMBase):
    id: int
    project_id: int
    student_id: Optional[int] = None
    initiated_by: Optional[int] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


# ========== partner.comparison_run_items ==========
class ComparisonRunItemCreate(MoneyBase):
    run_id: int
    model_name: str
    prompt_template_version_id: Optional[int] = None
    status: Optional[str] = None               # DB default 'pending'
    total_tokens: Optional[int] = None
    average_latency_ms: Optional[int] = None
    total_cost: Optional[Decimal] = None


class ComparisonRunItemUpdate(MoneyBase):
    model_name: Optional[str] = None
    prompt_template_version_id: Optional[int] = None
    status: Optional[str] = None
    total_tokens: Optional[int] = None
    average_latency_ms: Optional[int] = None
    total_cost: Optional[Decimal] = None


class ComparisonRunItemResponse(MoneyBase):
    id: int
    run_id: int
    model_name: str
    prompt_template_version_id: Optional[int] = None
    status: str
    total_tokens: Optional[int] = None
    average_latency_ms: Optional[int] = None
    total_cost: Optional[Decimal] = None
