# models/partner/catalog.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, Integer, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========= partner.provider_credentials =========
class ProviderCredential(Base):
    __tablename__ = "provider_credentials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    provider = Column(Text, nullable=False)                 # 예: openai, anthropic, google
    credential_label = Column(Text)                         # 키 식별 라벨
    api_key_encrypted = Column(Text, nullable=False)        # 원문 금지, 암호화 저장
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_validated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 관계(선택): OrgLlmSetting에서 참조
    org_settings = relationship("OrgLlmSetting", back_populates="provider_credential", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "provider", name="uq_provider_credentials_partner_provider"),
        Index("idx_provider_credentials_partner_provider", "partner_id", "provider"),
        Index("idx_provider_credentials_active", "is_active"),
        Index("idx_provider_credentials_validated", "last_validated_at"),
        {"schema": "partner"},
    )


class ModelCatalog(Base):
    __tablename__ = "model_catalog"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)
    modality = Column(Text, nullable=False, server_default=text("'chat'"))
    supports_parallel = Column(Boolean, nullable=False, server_default=text("false"))
    default_pricing = Column(JSONB)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 이 모델을 primary_model 로 쓰는 코스들
    primary_for_courses = relationship(
        "Course",
        back_populates="primary_model",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("provider", "model_name", name="uq_model_catalog_provider_model"),
        CheckConstraint(
            "modality IN ('chat','embedding','stt','image','tts','rerank')",
            name="chk_model_catalog_modality",
        ),
        CheckConstraint(
            "default_pricing IS NULL OR jsonb_typeof(default_pricing) = 'object'",
            name="chk_model_catalog_pricing_obj",
        ),
        Index("idx_model_catalog_provider_modality", "provider", "modality"),
        Index("idx_model_catalog_active", "is_active"),
        {"schema": "partner"},
    )


# ========= partner.org_llm_settings =========
class OrgLlmSetting(Base):
    __tablename__ = "org_llm_settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)

    default_chat_model = Column(Text, nullable=False)       # 예: gpt-4o-mini
    enable_parallel_mode = Column(Boolean, nullable=False, server_default=text("false"))
    daily_message_limit = Column(Integer)
    token_alert_threshold = Column(Integer)

    provider_credential_id = Column(
        BigInteger,
        ForeignKey("partner.provider_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="SET NULL"),
        nullable=True,
    )

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 관계
    provider_credential = relationship("ProviderCredential", back_populates="org_settings", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", name="uq_org_llm_settings_partner"),
        CheckConstraint("daily_message_limit IS NULL OR daily_message_limit >= 0", name="chk_org_llm_daily_limit_nonneg"),
        CheckConstraint("token_alert_threshold IS NULL OR token_alert_threshold >= 0", name="chk_org_llm_token_threshold_nonneg"),
        Index("idx_org_llm_settings_partner", "partner_id"),
        Index("idx_org_llm_settings_cred", "provider_credential_id"),
        {"schema": "partner"},
    )
