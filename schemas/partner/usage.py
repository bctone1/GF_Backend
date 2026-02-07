from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal, List, Any, Dict

from pydantic import ConfigDict, Field
from schemas.base import DecimalStr, ORMBase

# =========================
# type aliases
# =========================
UsageDimType = Literal["partner", "class", "enrollment", "student"]


# =========================
# partner.usage_events
# =========================
class UsageEventResponse(ORMBase):
    """
    원천 이벤트 로그(근거 데이터)
    """
    id: int
    request_id: str
    occurred_at: datetime

    partner_id: int
    class_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None
    session_id: Optional[int] = None

    request_type: str = Field(..., examples=["llm_chat", "embedding", "rerank", "stt"])
    provider: str = Field(..., examples=["openai", "anthropic", "google"])
    model_name: Optional[str] = Field(default=None, examples=["gpt-4o-mini", "claude-3-5-haiku"])

    total_tokens: int
    media_duration_seconds: int
    latency_ms: Optional[int] = None

    total_cost_usd: DecimalStr

    success: bool
    error_code: Optional[str] = None

    meta: Dict[str, Any] = Field(default_factory=dict)


class UsageEventListQuery(ORMBase):
    """
    usage_events 조회용 쿼리 파라미터(추천)
    """
    model_config = ConfigDict(from_attributes=False)

    # 기간(occurred_at 기준)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    # 필터
    request_type: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None

    class_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None
    session_id: Optional[int] = None

    success: Optional[bool] = None

    # paging
    offset: int = 0
    limit: int = Field(default=50, ge=1, le=500)


# =========================
# partner.usage_daily (선택: 추후 ETL용)
# =========================
class UsageDailyResponse(ORMBase):
    """
    일 단위 집계(추후 ETL/물리화용). 현재 on-read면 당장 사용 안 해도 됨.
    """
    id: int

    partner_id: int
    usage_date: date

    dim_type: UsageDimType
    dim_id: Optional[int] = None

    request_type: str
    provider: str
    model_name: Optional[str] = None

    request_count: int
    session_count: int

    total_tokens: int
    media_duration_seconds: int

    success_count: int
    error_count: int

    total_cost_usd: DecimalStr


class UsageDailyListQuery(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    dim_type: Optional[UsageDimType] = None
    dim_id: Optional[int] = None

    request_type: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None

    offset: int = 0
    limit: int = Field(default=200, ge=1, le=2000)


# =========================
# partner.usage_model_monthly (optional)
# =========================
class UsageModelMonthlyResponse(ORMBase):
    id: int

    partner_id: int
    month: date

    request_type: str
    provider: str
    model_name: str

    request_count: int
    total_tokens: int
    total_cost_usd: DecimalStr


# =========================
# (페이지 맞춤) analytics 응답 스키마들
# - on-read 집계 결과를 내려주는 용도
# =========================
class UsageKpiResponse(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    total_cost_usd: DecimalStr = Decimal("0")
    request_count: int = 0
    session_count: int = 0
    total_tokens: int = 0

    success_count: int = 0
    error_count: int = 0

    # on-read로 평균 정도는 가능(필요 시)
    avg_latency_ms: Optional[DecimalStr] = None

    active_students: int = 0
    active_classes: int = 0


class UsageTimeSeriesPoint(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    usage_date: date
    total_cost_usd: DecimalStr = Decimal("0")
    request_count: int = 0
    total_tokens: int = 0
    error_count: int = 0


class UsageModelBreakdownItem(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    provider: str
    model_name: Optional[str] = None

    total_cost_usd: DecimalStr = Decimal("0")
    request_count: int = 0
    total_tokens: int = 0
    share_pct: Optional[DecimalStr] = None


class UsageDimBreakdownItem(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    dim_type: UsageDimType
    dim_id: int
    dim_label: Optional[str] = None  # class_name / student_name 등 (조인해서 채우면 됨)

    total_cost_usd: DecimalStr = Decimal("0")
    request_count: int = 0
    total_tokens: int = 0
    error_count: int = 0


# =========================
# Feature Usage (analytics 보강)
# =========================
class FeatureUsageItem(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    student_count: int = 0
    total_students: int = 0
    usage_count: int = 0


class FeatureUsageResponse(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    compare_mode: FeatureUsageItem
    knowledge_base: FeatureUsageItem
    prompt: FeatureUsageItem
    project: FeatureUsageItem


class InstructorUsageAnalyticsResponse(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    kpi: UsageKpiResponse
    timeseries: List[UsageTimeSeriesPoint] = Field(default_factory=list)
    models: List[UsageModelBreakdownItem] = Field(default_factory=list)
    classes: List[UsageDimBreakdownItem] = Field(default_factory=list)
    students: List[UsageDimBreakdownItem] = Field(default_factory=list)
