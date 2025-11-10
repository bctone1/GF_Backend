# schemas/partner/usage.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict

from schemas.base import ORMBase, MoneyBase, Page


# ==============================
# READ-ONLY: usage_daily
# ==============================
class UsageDailyResponse(MoneyBase):
    id: int
    partner_id: int
    class_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None
    usage_date: date
    provider: str
    total_sessions: int
    total_messages: int
    total_tokens: int
    total_cost: Decimal


UsageDailyPage = Page[UsageDailyResponse]


# ==============================
# READ-ONLY: api_cost_daily
# ==============================
class ApiCostDailyResponse(MoneyBase):
    id: int
    partner_id: int
    usage_date: date
    provider: str
    total_cost: Decimal


ApiCostDailyPage = Page[ApiCostDailyResponse]


# ==============================
# READ-ONLY: model_usage_monthly
# ==============================
class ModelUsageMonthlyResponse(MoneyBase):
    id: int
    partner_id: int
    month: date  # YYYY-MM-01
    provider: str
    model_name: str
    session_count: int
    total_tokens: int
    total_cost: Decimal


ModelUsageMonthlyPage = Page[ModelUsageMonthlyResponse]


# ==============================
# usage_events_llm  (append-only 권장)
# ==============================
class UsageEventLLMCreate(MoneyBase):
    session_id: Optional[int] = None
    class_id: Optional[int] = None
    student_id: Optional[int] = None
    provider: str
    model_name: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    total_cost: Decimal = Decimal("0")
    success: Optional[bool] = None        # DB default true
    recorded_at: Optional[datetime] = None  # 서버 채움 권장


class UsageEventLLMUpdate(MoneyBase):
    model_config = ConfigDict(from_attributes=False)
    # 수정은 예외적으로만 허용
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    total_cost: Optional[Decimal] = None
    success: Optional[bool] = None
    recorded_at: Optional[datetime] = None


class UsageEventLLMResponse(MoneyBase):
    id: int
    session_id: Optional[int] = None
    class_id: Optional[int] = None
    student_id: Optional[int] = None
    provider: str
    model_name: str
    tokens_prompt: int
    tokens_completion: int
    total_cost: Decimal
    success: bool
    recorded_at: datetime


UsageEventLLMPage = Page[UsageEventLLMResponse]


# ==============================
# usage_events_stt  (append-only 권장)
# ==============================
class UsageEventSTTCreate(MoneyBase):
    session_id: Optional[int] = None
    class_id: Optional[int] = None
    student_id: Optional[int] = None
    provider: str
    media_duration_seconds: int = 0
    total_cost: Decimal = Decimal("0")
    recorded_at: Optional[datetime] = None


class UsageEventSTTUpdate(MoneyBase):
    model_config = ConfigDict(from_attributes=False)
    media_duration_seconds: Optional[int] = None
    total_cost: Optional[Decimal] = None
    recorded_at: Optional[datetime] = None


class UsageEventSTTResponse(MoneyBase):
    id: int
    session_id: Optional[int] = None
    class_id: Optional[int] = None
    student_id: Optional[int] = None
    provider: str
    media_duration_seconds: int
    total_cost: Decimal
    recorded_at: datetime


UsageEventSTTPage = Page[UsageEventSTTResponse]
