# models/partner/usage.py
# ETL 집계/로그 전용. 애플리케이션 직접 쓰기 금지 권장.

from sqlalchemy import (
    Column, BigInteger, Text, Integer, Date, DateTime, Numeric, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


# =========================
# partner.usage_events
# =========================
class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    request_id = Column(Text, nullable=False)  # 멱등키

    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)

    # drill-down
    class_id      = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="SET NULL"), nullable=True)
    enrollment_id = Column(BigInteger, ForeignKey("partner.enrollments.id", ondelete="SET NULL"), nullable=True)
    student_id    = Column(BigInteger, ForeignKey("partner.students.id", ondelete="SET NULL"), nullable=True)
    session_id    = Column(BigInteger, ForeignKey("partner.ai_sessions.id", ondelete="SET NULL"), nullable=True)

    request_type = Column(Text, nullable=False)  # "llm_chat", "embedding", ...

    provider   = Column(Text, nullable=False)
    model_name = Column(Text, nullable=True)

    # 토큰은 total만
    total_tokens = Column(Integer, nullable=False, server_default=text("0"))

    # 비토큰형 (필요 없으면 0)
    media_duration_seconds = Column(Integer, nullable=False, server_default=text("0"))

    latency_ms = Column(Integer, nullable=True)

    total_cost_usd = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    # 호출 성공실패 알려고 에러코드도 auth 에러인지 타임아웃인지
    success    = Column(Boolean, nullable=False, server_default=text("true"))
    error_code = Column(Text, nullable=True)

    # 확장 필드: provider별 raw usage, prompt/completion 등(일단임시)
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("request_id", name="uq_usage_events_request_id"),
        CheckConstraint(
            "total_tokens >= 0 AND media_duration_seconds >= 0 AND total_cost_usd >= 0",
            name="chk_usage_events_nonneg",
        ),
        Index("idx_usage_events_partner_time", "partner_id", "occurred_at"),
        Index("idx_usage_events_partner_type_time", "partner_id", "request_type", "occurred_at"),
        Index("idx_usage_events_partner_provider_model_time", "partner_id", "provider", "model_name", "occurred_at"),
        Index("idx_usage_events_class_time", "class_id", "occurred_at"),
        Index("idx_usage_events_student_time", "student_id", "occurred_at"),
        Index("idx_usage_events_success_time", "success", "occurred_at"),
        {"schema": "partner"},
    )


# =========================
# partner.usage_daily
# =========================
class UsageDaily(Base):
    __tablename__ = "usage_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False)

    # 강사/강의/학생을 쪼개지 않고 담기위함
    dim_type = Column(Text, nullable=False)   # "partner" | "class" | "enrollment" | "student"
    dim_id   = Column(BigInteger, nullable=True)

    request_type = Column(Text, nullable=False)

    provider   = Column(Text, nullable=False)
    model_name = Column(Text, nullable=True)

    # 카운트(KPI) - 최소만
    request_count = Column(Integer, nullable=False, server_default=text("0"))
    session_count = Column(Integer, nullable=False, server_default=text("0"))

    # 토큰/미디어 - 최소만
    total_tokens = Column(Integer, nullable=False, server_default=text("0"))
    media_duration_seconds = Column(Integer, nullable=False, server_default=text("0"))

    # 성공/실패
    success_count = Column(Integer, nullable=False, server_default=text("0"))
    error_count   = Column(Integer, nullable=False, server_default=text("0"))

    # 비용
    total_cost_usd = Column(Numeric(14, 4), nullable=False, server_default=text("0"))


    __table_args__ = (
        CheckConstraint(
            "dim_type IN ('partner','class','enrollment','student')",
            name="chk_usage_daily_dim_type",
        ),
        CheckConstraint(
            "(dim_type = 'partner' AND dim_id IS NULL) OR (dim_type <> 'partner' AND dim_id IS NOT NULL)",
            name="chk_usage_daily_dim_id_rule",
        ),
        CheckConstraint(
            "request_count >= 0 AND session_count >= 0 "
            "AND total_tokens >= 0 AND media_duration_seconds >= 0 "
            "AND success_count >= 0 AND error_count >= 0 AND total_cost_usd >= 0",
            name="chk_usage_daily_nonneg",
        ),

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
# partner.usage_model_monthly
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
