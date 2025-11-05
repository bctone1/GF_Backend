# schemas/partner/usage.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from schemas.base import ORMBase


# ========= partner.usage_daily (READ-ONLY) =========
class UsageDailyResponse(ORMBase):
    id: int
    project_id: int
    usage_date: date
    total_sessions: int
    total_messages: int
    total_tokens: int
    total_cost: Decimal


# ========= partner.api_cost_daily (READ-ONLY) =========
class ApiCostDailyResponse(ORMBase):
    id: int
    partner_id: int
    project_id: Optional[int] = None
    usage_date: date
    provider: str
    total_cost: Decimal


# ========= partner.model_usage_monthly (READ-ONLY) =========
class ModelUsageMonthlyResponse(ORMBase):
    id: int
    partner_id: int
    month: date
    model_name: str
    session_count: int
    total_tokens: int
    total_cost: Decimal


# ========= partner.usage_events_llm (READ-ONLY) =========
class UsageEventLLMResponse(ORMBase):
    id: int
    session_id: Optional[int] = None
    model_name: str
    tokens_prompt: int
    tokens_completion: int
    total_cost: Decimal
    success: bool
    recorded_at: datetime


# ========= partner.usage_events_stt (READ-ONLY) =========
class UsageEventSTTResponse(ORMBase):
    id: int
    session_id: Optional[int] = None
    provider: str
    media_duration_seconds: int
    total_cost: Decimal
    recorded_at: datetime
