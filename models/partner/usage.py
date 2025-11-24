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

    partner_id    = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    class_id      = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="SET NULL"), nullable=True)
    enrollment_id = Column(BigInteger, ForeignKey("partner.enrollments.id", ondelete="SET NULL"), nullable=True)
    student_id    = Column(BigInteger, ForeignKey("partner.students.id", ondelete="SET NULL"), nullable=True)

    usage_date = Column(Date, nullable=False)
    provider   = Column(Text, nullable=False)

    total_sessions = Column(Integer, nullable=False, server_default=text("0"))
    total_messages = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens   = Column(Integer, nullable=False, server_default=text("0"))
    total_cost     = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    __table_args__ = (
        # 최소 하나의 축 필요
        CheckConstraint(
            "(enrollment_id IS NOT NULL) OR (class_id IS NOT NULL) OR (student_id IS NOT NULL)",
            name="chk_usage_daily_any_dim",
        ),
        CheckConstraint("total_sessions >= 0 AND total_messages >= 0 AND total_tokens >= 0 AND total_cost >= 0",
                        name="chk_usage_daily_nonneg"),
        # 부분 유니크: 수강 단위 집계
        Index(
            "uq_usage_daily_enrollment",
            "enrollment_id", "usage_date", "provider",
            unique=True, postgresql_where=text("enrollment_id IS NOT NULL"),
        ),
        # 부분 유니크: 분반 단위 집계(수강 미지정)
        Index(
            "uq_usage_daily_class",
            "partner_id", "class_id", "usage_date", "provider",
            unique=True, postgresql_where=text("enrollment_id IS NULL AND class_id IS NOT NULL"),
        ),
        # 부분 유니크: 학생 단위 집계(수강·분반 미지정)
        Index(
            "uq_usage_daily_student",
            "partner_id", "student_id", "usage_date", "provider",
            unique=True, postgresql_where=text("enrollment_id IS NULL AND class_id IS NULL AND student_id IS NOT NULL"),
        ),
        Index("idx_usage_daily_enrollment_date", "enrollment_id", "usage_date"),
        Index("idx_usage_daily_class_date", "class_id", "usage_date"),
        Index("idx_usage_daily_student_date", "student_id", "usage_date"),
        {"schema": "partner"},
    )


# ========= partner.api_cost_daily =========
class ApiCostDaily(Base):
    __tablename__ = "api_cost_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False)
    provider   = Column(Text, nullable=False)
    total_cost = Column(Numeric(14, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("partner_id", "usage_date", "provider", name="uq_api_cost_daily_key"),
        CheckConstraint("total_cost >= 0", name="chk_api_cost_daily_cost_nonneg"),
        Index("idx_api_cost_daily_partner_date", "partner_id", "usage_date"),
        Index("idx_api_cost_daily_provider_date", "provider", "usage_date"),
        {"schema": "partner"},
    )


# ========= partner.model_usage_monthly =========
class ModelUsageMonthly(Base):
    __tablename__ = "model_usage_monthly"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    month      = Column(Date, nullable=False)             # YYYY-MM-01
    provider   = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)

    session_count = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens  = Column(Integer, nullable=False, server_default=text("0"))
    total_cost    = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("partner_id", "month", "provider", "model_name", name="uq_model_usage_monthly_key"),
        CheckConstraint("date_trunc('month', month::timestamp) = month::timestamp",
                        name="chk_model_usage_month_first_day"),
        CheckConstraint("session_count >= 0 AND total_tokens >= 0 AND total_cost >= 0",
                        name="chk_model_usage_monthly_nonneg"),
        Index("idx_model_usage_monthly_partner_month", "partner_id", "month"),
        Index("idx_model_usage_monthly_provider_model", "provider", "model_name"),
        {"schema": "partner"},
    )


# ========= partner.usage_events_llm =========
class UsageEventLLM(Base):
    __tablename__ = "usage_events_llm"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(BigInteger, ForeignKey("partner.ai_sessions.id", ondelete="SET NULL"), nullable=True)
    # ETL 편의용 축(옵션)
    class_id   = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(BigInteger, ForeignKey("partner.students.id", ondelete="SET NULL"), nullable=True)

    provider   = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)

    tokens_prompt     = Column(Integer, nullable=False, server_default=text("0"))
    tokens_completion = Column(Integer, nullable=False, server_default=text("0"))
    total_cost        = Column(Numeric(14, 4), nullable=False, server_default=text("0"))
    success           = Column(Boolean, nullable=False, server_default=text("true"))

    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("tokens_prompt >= 0 AND tokens_completion >= 0 AND total_cost >= 0",
                        name="chk_usage_events_llm_nonneg"),
        Index("idx_usage_events_llm_session_time", "session_id", "recorded_at"),
        Index("idx_usage_events_llm_provider_model_time", "provider", "model_name", "recorded_at"),
        Index("idx_usage_events_llm_success_time", "success", "recorded_at"),
        Index("idx_usage_events_llm_class_time", "class_id", "recorded_at"),
        Index("idx_usage_events_llm_student_time", "student_id", "recorded_at"),
        {"schema": "partner"},
    )


# ========= partner.usage_events_stt =========
class UsageEventSTT(Base):
    __tablename__ = "usage_events_stt"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(BigInteger, ForeignKey("partner.ai_sessions.id", ondelete="SET NULL"), nullable=True)
    # ETL 편의용 축(옵션)
    class_id   = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(BigInteger, ForeignKey("partner.students.id", ondelete="SET NULL"), nullable=True)

    provider = Column(Text, nullable=False)

    media_duration_seconds = Column(Integer, nullable=False, server_default=text("0"))
    total_cost             = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("media_duration_seconds >= 0 AND total_cost >= 0",
                        name="chk_usage_events_stt_nonneg"),
        Index("idx_usage_events_stt_session_time", "session_id", "recorded_at"),
        Index("idx_usage_events_stt_provider_time", "provider", "recorded_at"),
        Index("idx_usage_events_stt_class_time", "class_id", "recorded_at"),
        Index("idx_usage_events_stt_student_time", "student_id", "recorded_at"),
        {"schema": "partner"},
    )
