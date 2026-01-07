# schemas/partner/usage.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal, List

from pydantic import ConfigDict, Field
from schemas.base import ORMBase

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
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

    id: int
    request_id: str
    turn_id: Optional[int] = None

    occurred_at: datetime

    partner_id: int
    class_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None

    session_id: Optional[int] = None
    response_id: Optional[int] = None

    request_type: str = Field(..., examples=["llm_chat", "embedding", "rerank", "stt"])
    provider: str = Field(..., examples=["openai", "anthropic", "google"])
    model_name: Optional[str] = Field(default=None, examples=["gpt-4o-mini", "claude-3-5-haiku"])

    tokens_prompt: int
    tokens_completion: int
    total_tokens: int

    media_duration_seconds: int

    latency_ms: Optional[int] = None

    total_cost_usd: Decimal

    success: bool
    error_code: Optional[str] = None


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

    success: Optional[bool] = None

    # paging
    offset: int = 0
    limit: int = Field(default=50, ge=1, le=500)


# =========================
# partner.usage_daily
# =========================
class UsageDailyResponse(ORMBase):
    """
    instructor-analytics 페이지 렌더링용 일 단위 집계
    """
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

    id: int

    partner_id: int
    usage_date: date

    dim_type: UsageDimType
    dim_id: Optional[int] = None

    request_type: str
    provider: str
    model_name: Optional[str] = None

    request_count: int
    turn_count: int
    session_count: int
    message_count: int

    tokens_prompt: int
    tokens_completion: int
    total_tokens: int
    media_duration_seconds: int

    success_count: int
    error_count: int

    total_cost_usd: Decimal

    avg_latency_ms: Optional[Decimal] = None
    p95_latency_ms: Optional[Decimal] = None


class UsageDailyListQuery(ORMBase):
    """
    usage_daily 조회용 쿼리 파라미터(추천)
    """
    model_config = ConfigDict(from_attributes=False)

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    dim_type: Optional[UsageDimType] = None
    dim_id: Optional[int] = None

    request_type: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None


# =========================
# partner.usage_model_monthly (optional)
# =========================
class UsageModelMonthlyResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

    id: int

    partner_id: int
    month: date

    request_type: str
    provider: str
    model_name: str

    request_count: int
    total_tokens: int
    total_cost_usd: Decimal


# =========================
# (페이지 맞춤) analytics 응답 스키마들
# =========================
class UsageKpiResponse(ORMBase):
    """
    상단 KPI 카드/요약용 (usage_daily 기반 집계 결과)
    """
    model_config = ConfigDict(from_attributes=False, json_encoders={Decimal: str})

    total_cost_usd: Decimal = Decimal("0")
    request_count: int = 0
    turn_count: int = 0
    session_count: int = 0
    message_count: int = 0
    total_tokens: int = 0

    success_count: int = 0
    error_count: int = 0

    avg_latency_ms: Optional[Decimal] = None
    p95_latency_ms: Optional[Decimal] = None

    active_students: int = 0
    active_classes: int = 0


class UsageTimeSeriesPoint(ORMBase):
    """
    비용/요청 추이 차트용
    """
    model_config = ConfigDict(from_attributes=False, json_encoders={Decimal: str})

    usage_date: date
    total_cost_usd: Decimal = Decimal("0")
    request_count: int = 0
    total_tokens: int = 0
    error_count: int = 0


class UsageModelBreakdownItem(ORMBase):
    """
    모델별 점유율/랭킹
    """
    model_config = ConfigDict(from_attributes=False, json_encoders={Decimal: str})

    provider: str
    model_name: Optional[str] = None

    total_cost_usd: Decimal = Decimal("0")
    request_count: int = 0
    total_tokens: int = 0

    # UI에서 계산해도 되지만, 백엔드에서 내려주면 편함
    share_pct: Optional[Decimal] = None


class UsageDimBreakdownItem(ORMBase):
    """
    클래스별/학생별 랭킹(usage_daily dim_type 기반)
    """
    model_config = ConfigDict(from_attributes=False, json_encoders={Decimal: str})

    dim_type: UsageDimType
    dim_id: int
    dim_label: Optional[str] = None  # class_name / student_name 등 (조인해서 채우면 됨)

    total_cost_usd: Decimal = Decimal("0")
    request_count: int = 0
    total_tokens: int = 0
    error_count: int = 0


class InstructorUsageAnalyticsResponse(ORMBase):
    """
    instructor-analytics 한 번에 내려줄 때 쓰는 통합 응답(선택)
    """
    model_config = ConfigDict(from_attributes=False, json_encoders={Decimal: str})

    kpi: UsageKpiResponse
    timeseries: List[UsageTimeSeriesPoint] = Field(default_factory=list)
    models: List[UsageModelBreakdownItem] = Field(default_factory=list)
    classes: List[UsageDimBreakdownItem] = Field(default_factory=list)
    students: List[UsageDimBreakdownItem] = Field(default_factory=list)
