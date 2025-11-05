# models/settings.py
from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, Boolean, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.sql import func, text
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


# ========== supervisor.platform_settings ==========
class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    setting_id = Column(BigInteger, primary_key=True, autoincrement=True)
    category = Column(String(64), nullable=False)
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=True)
    value_type = Column(String(32), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(BigInteger, ForeignKey("supervisor.users.user_id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("category", "key", name="uq_platform_settings_category_key"),
        Index("idx_platform_settings_category", "category"),
        Index("idx_platform_settings_key", "key"),
        {"schema": "supervisor"},
    )


# ========== supervisor.api_keys ==========
class ApiKey(Base):
    __tablename__ = "api_keys"

    api_key_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    key_hash = Column(Text, nullable=False, unique=True)  # 원문 저장 금지
    status = Column(String(32), nullable=False, server_default=text("'active'"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(BigInteger, ForeignKey("supervisor.users.user_id", ondelete="SET NULL"), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('active','revoked','disabled')", name="chk_api_keys_status"),
        Index("idx_api_keys_status", "status"),
        Index("idx_api_keys_last_used", "last_used_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.rate_limits ==========
class RateLimit(Base):
    __tablename__ = "rate_limits"

    limit_id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 기본값: 플랜 단위 / 오버라이드: 조직 단위
    plan_id = Column(BigInteger, ForeignKey("supervisor.plans.plan_id", ondelete="CASCADE"), nullable=True)
    organization_id = Column(BigInteger, ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"), nullable=True)

    limit_type = Column(String(64), nullable=False)   # 예: 'requests_per_min', 'tokens_per_day'
    limit_value = Column(Integer, nullable=False)
    window_sec = Column(Integer, nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(BigInteger, ForeignKey("supervisor.users.user_id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        # plan_id 또는 organization_id 중 정확히 하나만 설정
        CheckConstraint(
            "(plan_id IS NOT NULL AND organization_id IS NULL) OR (plan_id IS NULL AND organization_id IS NOT NULL)",
            name="chk_rate_limits_scope_xor",
        ),
        # 고유키 (scope, key) 구현: 플랜 범위
        Index(
            "uq_rate_limits_plan",
            "plan_id",
            "limit_type",
            unique=True,
            postgresql_where=text("plan_id IS NOT NULL AND organization_id IS NULL"),
        ),
        # 고유키 (scope, key) 구현: 조직 범위
        Index(
            "uq_rate_limits_org",
            "organization_id",
            "limit_type",
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL"),
        ),
        Index("idx_rate_limits_type", "limit_type"),
        {"schema": "supervisor"},
    )


# ========== supervisor.webhooks ==========
class Webhook(Base):
    __tablename__ = "webhooks"

    webhook_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(BigInteger, ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(64), nullable=False)  # 예: 'session.created'
    target_url = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, server_default=text("'active'"))
    secret = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('active','disabled')", name="chk_webhooks_status"),
        Index("idx_webhooks_org", "organization_id"),
        Index("idx_webhooks_event", "event_type"),
        Index("idx_webhooks_status", "status"),
        {"schema": "supervisor"},
    )


# ========== supervisor.llm_providers ==========
class LlmProvider(Base):
    __tablename__ = "llm_providers"

    provider_id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_name = Column(String(64), nullable=False)      # 예: 'openai', 'anthropic'
    api_key = Column(Text, nullable=False)                  # 저장 시 암호화 계층 권장
    default_model = Column(String(128), nullable=True)
    temperature = Column(String(10), nullable=True)         # 정밀 필요시 NUMERIC으로 전환
    max_tokens = Column(Integer, nullable=True)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, server_default=text("'active'"))

    __table_args__ = (
        CheckConstraint("status IN ('active','inactive','deprecated')", name="chk_llm_providers_status"),
        Index("idx_llm_providers_name", "provider_name"),
        Index("idx_llm_providers_status", "status"),
        {"schema": "supervisor"},
    )


# ========== supervisor.email_settings ==========
class EmailSetting(Base):
    __tablename__ = "email_settings"

    email_setting_id = Column(BigInteger, primary_key=True, autoincrement=True)
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, nullable=False)
    tls_enabled = Column(Boolean, nullable=False, server_default=text("true"))

    username = Column(String(255), nullable=True)
    password_encrypted = Column(Text, nullable=True)

    sender_name = Column(String(128), nullable=True)
    sender_email = Column(String(255), nullable=True)
    reply_to = Column(String(255), nullable=True)

    template_config_json = Column(JSONB, nullable=True)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_email_settings_host_port", "smtp_host", "smtp_port"),
        {"schema": "supervisor"},
    )


# ========== supervisor.integrations ==========
class Integration(Base):
    __tablename__ = "integrations"

    integration_id = Column(BigInteger, primary_key=True, autoincrement=True)
    type = Column(String(64), nullable=False)       # 예: 'slack', 'zendesk', 'github'
    config_json = Column(JSONB, nullable=False)
    status = Column(String(32), nullable=False, server_default=text("'active'"))
    last_tested_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('active','inactive')", name="chk_integrations_status"),
        Index("idx_integrations_type", "type"),
        Index("idx_integrations_status", "status"),
        {"schema": "supervisor"},
    )
