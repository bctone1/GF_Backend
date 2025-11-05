# schemas/supervisor/api_usage.py
from __future__ import annotations
from typing import Optional
from decimal import Decimal
from datetime import datetime
from schemas.base import MoneyBase


# ========== supervisor.api_usage ==========
class ApiUsageCreate(MoneyBase):
    organization_id: int
    user_id: Optional[int] = None

    provider: str
    endpoint: str

    tokens: int = 0
    cost: Decimal = Decimal("0")

    status: str                      # 'success' | 'error' | 'timeout' | 'rate_limited'
    response_time_ms: Optional[int] = None

    requested_at: Optional[datetime] = None


class ApiUsageUpdate(MoneyBase):
    # 원장 성격이므로 보통 업데이트는 최소화. 필요 시 아래 필드만 허용.
    tokens: Optional[int] = None
    cost: Optional[Decimal] = None
    status: Optional[str] = None
    response_time_ms: Optional[int] = None
    requested_at: Optional[datetime] = None


class ApiUsageResponse(MoneyBase):
    usage_id: int

    organization_id: int
    user_id: Optional[int] = None

    provider: str
    endpoint: str

    tokens: int
    cost: Decimal

    status: str
    response_time_ms: Optional[int] = None
    requested_at: datetime
