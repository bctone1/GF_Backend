# models/user/activity.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, DateTime, Date, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base


# ========== user.user_activity_events ==========
class UserActivityEvent(Base):
    __tablename__ = "user_activity_events"

    event_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(Text, nullable=False)
    related_type = Column(Text, nullable=True)  # 'project' | 'document' | 'prompt' | ...
    related_id = Column(BigInteger, nullable=True)
    meta = Column("metadata", JSONB, nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_user_activity_user_time", "user_id", "occurred_at"),
        Index("idx_user_activity_type_time", "event_type", "occurred_at"),
        Index("idx_user_activity_related", "related_type", "related_id"),
        {"schema": "user"},
    )


# ========== user.usage_summaries ==========
class UsageSummary(Base):
    __tablename__ = "usage_summaries"

    summary_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    metric_type = Column(Text, nullable=False)            # e.g., 'sessions','messages','practice_hours'
    metric_value = Column(Numeric(18, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "period_start", "metric_type", name="uq_usage_summaries_user_period_metric"),
        CheckConstraint("period_end >= period_start", name="chk_usage_summaries_period_valid"),
        CheckConstraint("metric_value >= 0", name="chk_usage_summaries_value_nonneg"),
        Index("idx_usage_summaries_user_period", "user_id", "period_start"),
        {"schema": "user"},
    )


# ========== user.model_usage_stats ==========
class ModelUsageStat(Base):
    __tablename__ = "model_usage_stats"

    stat_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name = Column(Text, nullable=False)

    usage_count = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens = Column(BigInteger, nullable=False, server_default=text("0"))
    avg_latency_ms = Column(Integer, nullable=True)
    satisfaction_score = Column(Numeric(3, 2), nullable=True)  # 0.00~5.00
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "model_name", name="uq_model_usage_stats_user_model"),
        CheckConstraint("usage_count >= 0", name="chk_model_usage_stats_count_nonneg"),
        CheckConstraint("total_tokens >= 0", name="chk_model_usage_stats_tokens_nonneg"),
        CheckConstraint("avg_latency_ms IS NULL OR avg_latency_ms >= 0", name="chk_model_usage_stats_latency_nonneg"),
        CheckConstraint(
            "satisfaction_score IS NULL OR (satisfaction_score >= 0 AND satisfaction_score <= 5)",
            name="chk_model_usage_stats_sat_0_5",
        ),
        Index("idx_model_usage_stats_user", "user_id"),
        Index("idx_model_usage_stats_model", "model_name"),
        Index("idx_model_usage_stats_last_used", "last_used_at"),
        {"schema": "user"},
    )


# ========== user.user_achievements ==========
class UserAchievement(Base):
    __tablename__ = "user_achievements"

    achievement_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    achievement_key = Column(Text, nullable=False)        # e.g., 'first_100_messages'
    earned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column("metadata", JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_key", name="uq_user_achievements_user_key"),
        Index("idx_user_achievements_user_time", "user_id", "earned_at"),
        {"schema": "user"},
    )
