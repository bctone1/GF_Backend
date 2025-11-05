# models/partner/usage.py
# ETL 집계 전용. 애플리케이션 직접 쓰기 금지 권장.
from sqlalchemy import (
    Column, BigInteger, Text, Integer, Date, DateTime, Numeric, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from models.base import Base


# ========= partner.usage_daily =========
class UsageDaily(Base):
    __tablename__ = "usage_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    usage_date = Column(Date, nullable=False)

    total_sessions = Column(Integer, nullable=False, server_default=text("0"))
    total_messages = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens = Column(Integer, nullable=False, server_default=text("0"))
    total_cost = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("project_id", "usage_date", name="uq_usage_daily_project_date"),
        CheckConstraint("total_sessions >= 0", name="chk_usage_daily_sessions_nonneg"),
        CheckConstraint("total_messages >= 0", name="chk_usage_daily_messages_nonneg"),
        CheckConstraint("total_tokens >= 0", name="chk_usage_daily_tokens_nonneg"),
        CheckConstraint("total_cost >= 0", name="chk_usage_daily_cost_nonneg"),
        Index("idx_usage_daily_project_date", "project_id", "usage_date"),
        {"schema": "partner"},
    )


# ========= partner.api_cost_daily =========
class ApiCostDaily(Base):
    __tablename__ = "api_cost_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="SET NULL"),
        nullable=True,  # NULL 허용
    )

    usage_date = Column(Date, nullable=False)
    provider = Column(Text, nullable=False)
    total_cost = Column(Numeric(14, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "partner_id", "usage_date", "provider", "project_id",
            name="uq_api_cost_daily_key"
        ),
        CheckConstraint("total_cost >= 0", name="chk_api_cost_daily_cost_nonneg"),
        Index("idx_api_cost_daily_partner_date", "partner_id", "usage_date"),
        Index("idx_api_cost_daily_provider_date", "provider", "usage_date"),
        {"schema": "partner"},
    )


# ========= partner.model_usage_monthly =========
class ModelUsageMonthly(Base):
    __tablename__ = "model_usage_monthly"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    month = Column(Date, nullable=False)             # YYYY-MM-01 관례
    model_name = Column(Text, nullable=False)

    session_count = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens = Column(Integer, nullable=False, server_default=text("0"))
    total_cost = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("partner_id", "month", "model_name", name="uq_model_usage_monthly_key"),
        CheckConstraint("session_count >= 0", name="chk_model_usage_monthly_sessions_nonneg"),
        CheckConstraint("total_tokens >= 0", name="chk_model_usage_monthly_tokens_nonneg"),
        CheckConstraint("total_cost >= 0", name="chk_model_usage_monthly_cost_nonneg"),
        Index("idx_model_usage_monthly_partner_month", "partner_id", "month"),
        Index("idx_model_usage_monthly_model", "model_name"),
        {"schema": "partner"},
    )


# ========= partner.usage_events_llm =========
class UsageEventLLM(Base):
    __tablename__ = "usage_events_llm"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(
        BigInteger,
        ForeignKey("partner.ai_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_name = Column(Text, nullable=False)

    tokens_prompt = Column(Integer, nullable=False, server_default=text("0"))
    tokens_completion = Column(Integer, nullable=False, server_default=text("0"))
    total_cost = Column(Numeric(14, 4), nullable=False, server_default=text("0"))
    success = Column(Boolean, nullable=False, server_default=text("true"))

    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("tokens_prompt >= 0", name="chk_usage_events_llm_prompt_nonneg"),
        CheckConstraint("tokens_completion >= 0", name="chk_usage_events_llm_completion_nonneg"),
        CheckConstraint("total_cost >= 0", name="chk_usage_events_llm_cost_nonneg"),
        Index("idx_usage_events_llm_session_time", "session_id", "recorded_at"),
        Index("idx_usage_events_llm_model_time", "model_name", "recorded_at"),
        Index("idx_usage_events_llm_success_time", "success", "recorded_at"),
        {"schema": "partner"},
    )


# ========= partner.usage_events_stt =========
class UsageEventSTT(Base):
    __tablename__ = "usage_events_stt"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(
        BigInteger,
        ForeignKey("partner.ai_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider = Column(Text, nullable=False)

    media_duration_seconds = Column(Integer, nullable=False, server_default=text("0"))
    total_cost = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("media_duration_seconds >= 0", name="chk_usage_events_stt_duration_nonneg"),
        CheckConstraint("total_cost >= 0", name="chk_usage_events_stt_cost_nonneg"),
        Index("idx_usage_events_stt_session_time", "session_id", "recorded_at"),
        Index("idx_usage_events_stt_provider_time", "provider", "recorded_at"),
        {"schema": "partner"},
    )
