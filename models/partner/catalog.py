# models/partner/catalog.py
from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, Integer, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base


# ========= partner.provider_credentials =========
class ProviderCredential(Base):
    __tablename__ = "provider_credentials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(Text, nullable=False)                 # 예: openai, anthropic, google
    credential_label = Column(Text, nullable=True)          # 키 식별 라벨
    api_key_encrypted = Column(Text, nullable=False)        # 원문 금지, 암호화 저장
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("partner_id", "provider", name="uq_provider_credentials_partner_provider"),
        Index("idx_provider_credentials_partner_provider", "partner_id", "provider"),
        Index("idx_provider_credentials_active", "is_active"),
        Index("idx_provider_credentials_validated", "last_validated_at"),
        {"schema": "partner"},
    )


# ========= partner.model_catalog =========
class ModelCatalog(Base):
    __tablename__ = "model_catalog"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)
    modality = Column(Text, nullable=False, server_default=text("'chat'"))  # chat | embedding | stt | image ...
    supports_parallel = Column(Boolean, nullable=False, server_default=text("false"))
    default_pricing = Column(JSONB, nullable=True)          # {input_per_1k, output_per_1k, audio_per_sec, ...}
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("provider", "model_name", name="uq_model_catalog_provider_model"),
        Index("idx_model_catalog_provider_modality", "provider", "modality"),
        Index("idx_model_catalog_active", "is_active"),
        {"schema": "partner"},
    )


# ========= partner.org_llm_settings =========
class OrgLlmSetting(Base):
    __tablename__ = "org_llm_settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    default_chat_model = Column(Text, nullable=False)       # 예: gpt-4o-mini
    enable_parallel_mode = Column(Boolean, nullable=False, server_default=text("false"))
    daily_message_limit = Column(Integer, nullable=True)
    token_alert_threshold = Column(Integer, nullable=True)

    provider_credential_id = Column(
        BigInteger,
        ForeignKey("partner.provider_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("partner_id", name="uq_org_llm_settings_partner"),
        CheckConstraint("daily_message_limit IS NULL OR daily_message_limit >= 0", name="chk_org_llm_daily_limit_nonneg"),
        CheckConstraint("token_alert_threshold IS NULL OR token_alert_threshold >= 0", name="chk_org_llm_token_threshold_nonneg"),
        Index("idx_org_llm_settings_partner", "partner_id"),
        {"schema": "partner"},
    )
