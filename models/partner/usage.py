# models/partner/usage.py
# ETL 집계/로그 전용. 애플리케이션 직접 쓰기 금지 권장.

from sqlalchemy import (
    Column, BigInteger, Text, Integer, Date, DateTime, Numeric, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from models.base import Base


# =========================
# partner.usage_events
# - 원천 이벤트(로그) 1장 통일
# - instructor-analytics의 "정확한 근거 데이터"
# =========================
class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 중복 방지 / 멱등키(재시도/ETL 재적재 방어)
    # 예: "{provider}:{request_uuid}" 또는 LLM 응답 row의 uuid 등을 넣어라
    request_id = Column(Text, nullable=False)

    # 예: practice_responses.turn_id / session_messages.turn_id 같은 개념
    turn_id = Column(BigInteger, nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # 강사 통계의 최상위 축: partner_id는 이벤트에 박아두는 게 좋다(조인 비용 절감)
    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)

    # drill-down용 축(필요한 만큼)
    class_id      = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="SET NULL"), nullable=True)
    enrollment_id = Column(BigInteger, ForeignKey("partner.enrollments.id", ondelete="SET NULL"), nullable=True)
    student_id    = Column(BigInteger, ForeignKey("partner.students.id", ondelete="SET NULL"), nullable=True)

    # (있으면 좋은 연결키)
    session_id   = Column(BigInteger, ForeignKey("partner.ai_sessions.id", ondelete="SET NULL"), nullable=True)
    response_id  = Column(BigInteger, nullable=True)  # FK를 걸 수 있으면 거는 게 베스트(예: partner.practice_responses.id)

    # 어떤 종류의 사용량인지: "llm_chat", "embedding", "rerank", "stt", "tts", "image", ...
    request_type = Column(Text, nullable=False)

    provider   = Column(Text, nullable=False)
    model_name = Column(Text, nullable=True)  # STT 같은 경우 모델이 없으면 NULL 허용

    # 토큰(LLM/Embedding/Rerank 등)
    tokens_prompt     = Column(Integer, nullable=False, server_default=text("0"))
    tokens_completion = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens      = Column(Integer, nullable=False, server_default=text("0"))

    # 음성(STT/TTS 등) 같은 비토큰형 지표
    media_duration_seconds = Column(Integer, nullable=False, server_default=text("0"))

    # 응답속도 KPI용
    latency_ms = Column(Integer, nullable=True)

    # 비용(가능하면 이벤트 단위에서 확정 금액을 적재)
    total_cost_usd = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    # 성공/실패 & 에러 분석
    success    = Column(Boolean, nullable=False, server_default=text("true"))
    error_code = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("request_id", name="uq_usage_events_request_id"),

        CheckConstraint(
            "tokens_prompt >= 0 AND tokens_completion >= 0 AND total_tokens >= 0 "
            "AND media_duration_seconds >= 0 AND total_cost_usd >= 0",
            name="chk_usage_events_nonneg",
        ),

        Index("idx_usage_events_partner_time", "partner_id", "occurred_at"),
        Index("idx_usage_events_partner_type_time", "partner_id", "request_type", "occurred_at"),
        Index("idx_usage_events_partner_provider_model_time", "partner_id", "provider", "model_name", "occurred_at"),
        Index("idx_usage_events_class_time", "class_id", "occurred_at"),
        Index("idx_usage_events_student_time", "student_id", "occurred_at"),
        Index("idx_usage_events_success_time", "success", "occurred_at"),
        Index("idx_usage_events_turn_id", "turn_id"),
        {"schema": "partner"},
    )


# =========================
# partner.usage_daily
# - instructor-analytics 페이지를 "빠르게" 렌더링하기 위한 일 단위 집계
# - KPI/추이/모델별/클래스별을 다 커버하려면 "dimension 방식"이 제일 깔끔해
# =========================
class UsageDaily(Base):
    __tablename__ = "usage_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False)  # 로컬 기준(Asia/Seoul 등)으로 ETL에서 끊어라

    # 집계의 기준 축
    # dim_type: "partner" | "class" | "enrollment" | "student"
    dim_type = Column(Text, nullable=False)
    dim_id   = Column(BigInteger, nullable=True)

    # 어떤 종류의 사용량 집계인지
    request_type = Column(Text, nullable=False)

    provider   = Column(Text, nullable=False)
    model_name = Column(Text, nullable=True)

    # 카운트류(KPI)
    request_count  = Column(Integer, nullable=False, server_default=text("0"))   # 이벤트 수(= usage_events row 수)
    turn_count     = Column(Integer, nullable=False, server_default=text("0"))   # 질문 수(= distinct turn_id 등), 없으면 0 유지 가능
    session_count  = Column(Integer, nullable=False, server_default=text("0"))   # distinct session_id (가능하면)
    message_count  = Column(Integer, nullable=False, server_default=text("0"))   # 필요하면(LLM chat만)

    # 토큰/미디어
    tokens_prompt     = Column(Integer, nullable=False, server_default=text("0"))
    tokens_completion = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens      = Column(Integer, nullable=False, server_default=text("0"))
    media_duration_seconds = Column(Integer, nullable=False, server_default=text("0"))

    # 성공/실패
    success_count = Column(Integer, nullable=False, server_default=text("0"))
    error_count   = Column(Integer, nullable=False, server_default=text("0"))

    # 비용
    total_cost_usd = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    # 응답시간(ETL에서 평균/백분위 계산해 넣기)
    avg_latency_ms = Column(Numeric(14, 2), nullable=True)
    p95_latency_ms = Column(Numeric(14, 2), nullable=True)

    __table_args__ = (
        # dim_type 규칙
        CheckConstraint(
            "dim_type IN ('partner','class','enrollment','student')",
            name="chk_usage_daily_dim_type",
        ),
        # partner 집계면 dim_id는 NULL, 나머지는 dim_id 필수
        CheckConstraint(
            "(dim_type = 'partner' AND dim_id IS NULL) OR (dim_type <> 'partner' AND dim_id IS NOT NULL)",
            name="chk_usage_daily_dim_id_rule",
        ),
        CheckConstraint(
            "request_count >= 0 AND turn_count >= 0 AND session_count >= 0 AND message_count >= 0 "
            "AND tokens_prompt >= 0 AND tokens_completion >= 0 AND total_tokens >= 0 "
            "AND media_duration_seconds >= 0 AND success_count >= 0 AND error_count >= 0 AND total_cost_usd >= 0",
            name="chk_usage_daily_nonneg",
        ),

        # model_name NULL 때문에 유니크가 깨질 수 있어서 coalesce로 키 안정화
        Index(
            "uq_usage_daily_key",
            "partner_id", "usage_date", "dim_type", "dim_id", "request_type", "provider",
            text("coalesce(model_name,'')"),
            unique=True,
        ),

        Index("idx_usage_daily_partner_date", "partner_id", "usage_date"),
        Index("idx_usage_daily_partner_dim_date", "partner_id", "dim_type", "usage_date"),
        Index("idx_usage_daily_type_provider_date", "request_type", "provider", "usage_date"),
        {"schema": "partner"},
    )


# =========================
# (선택) partner.usage_model_monthly
# - 월간 모델 차트가 자주 쓰이고 데이터가 커지면 daily->monthly도 ETL로 내려라
# =========================
class UsageModelMonthly(Base):
    __tablename__ = "usage_model_monthly"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    month      = Column(Date, nullable=False)  # YYYY-MM-01
    request_type = Column(Text, nullable=False)

    provider   = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)

    request_count = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens  = Column(Integer, nullable=False, server_default=text("0"))
    total_cost_usd = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint(
            "partner_id", "month", "request_type", "provider", "model_name",
            name="uq_usage_model_monthly_key",
        ),
        CheckConstraint(
            "date_trunc('month', month::timestamp) = month::timestamp",
            name="chk_usage_model_month_first_day",
        ),
        CheckConstraint(
            "request_count >= 0 AND total_tokens >= 0 AND total_cost_usd >= 0",
            name="chk_usage_model_monthly_nonneg",
        ),
        Index("idx_usage_model_monthly_partner_month", "partner_id", "month"),
        Index("idx_usage_model_monthly_provider_model", "provider", "model_name"),
        {"schema": "partner"},
    )
