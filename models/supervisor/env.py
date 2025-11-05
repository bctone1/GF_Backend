# models/env.py
from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, DateTime, Date, Integer, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
    # JSONB only where needed
from sqlalchemy.sql import func
from models.base import Base


# ========== supervisor.env_variables ==========
class EnvVariable(Base):
    __tablename__ = "env_variables"

    env_id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True)
    value = Column(Text, nullable=True)
    scope = Column(String(64), nullable=False)                 # global | org | user 등
    encrypted = Column(Boolean, nullable=False, server_default=text("false"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(BigInteger, nullable=True)              # FK 생략(로그 성격)

    __table_args__ = (
        Index("idx_env_variables_scope", "scope"),
        {"schema": "supervisor"},
    )


# ========== supervisor.danger_zone_logs ==========
class DangerZoneLog(Base):
    __tablename__ = "danger_zone_logs"

    action_id = Column(BigInteger, primary_key=True, autoincrement=True)
    action_type = Column(String(64), nullable=False)           # purge_data | rotate_keys | etc
    performed_by = Column(BigInteger, nullable=True)           # FK 생략
    performed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_danger_zone_logs_type_time", "action_type", "performed_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.feature_toggles ==========
# 요구사항: (key, scope, target_id) 유니크. 롤아웃 비율 옵션.
class FeatureToggle(Base):
    __tablename__ = "feature_toggles"

    toggle_id = Column(BigInteger, primary_key=True, autoincrement=True)
    feature_name = Column(String(128), nullable=False)         # 토글 키
    is_enabled = Column(Boolean, nullable=False, server_default=text("false"))
    scope = Column(String(64), nullable=True)                  # global | org | user
    target_id = Column(BigInteger, nullable=True)              # scope가 org/user일 때 대상 ID
    rollout_pct = Column(Integer, nullable=True)               # 0~100, 옵션

    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("feature_name", "scope", "target_id", name="uq_feature_toggles_key_scope_target"),
        CheckConstraint(
            "rollout_pct IS NULL OR (rollout_pct BETWEEN 0 AND 100)",
            name="chk_feature_toggles_rollout_pct",
        ),
        Index("idx_feature_toggles_name", "feature_name"),
        Index("idx_feature_toggles_enabled", "is_enabled"),
        {"schema": "supervisor"},
    )


# ========== supervisor.usage_features ==========
class UsageFeature(Base):
    __tablename__ = "usage_features"

    record_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_name = Column(String(128), nullable=False)
    usage_count = Column(BigInteger, nullable=False, server_default=text("0"))
    period = Column(Date, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "feature_name", "period", name="uq_usage_features_org_feature_period"),
        Index("idx_usage_features_org_period", "organization_id", "period"),
        Index("idx_usage_features_feature_period", "feature_name", "period"),
        CheckConstraint("usage_count >= 0", name="chk_usage_features_nonneg"),
        {"schema": "supervisor"},
    )


# ========== supervisor.ai_insights ==========
class AiInsight(Base):
    __tablename__ = "ai_insights"

    insight_id = Column(BigInteger, primary_key=True, autoincrement=True)
    category = Column(String(64), nullable=False)          # anomaly | churn | growth 등
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    data_points_json = Column(JSONB, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_ai_insights_category_time", "category", "generated_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.forecasts ==========
class Forecast(Base):
    __tablename__ = "forecasts"

    forecast_id = Column(BigInteger, primary_key=True, autoincrement=True)
    metric_type = Column(String(64), nullable=False)       # mrr | dau | tokens 등
    period = Column(Date, nullable=False)                  # 보통 월 기준 YYYY-MM-01
    value = Column(Numeric(18, 4), nullable=False)
    model_info = Column(JSONB, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confidence_interval_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_forecasts_metric_period", "metric_type", "period"),
        {"schema": "supervisor"},
    )
