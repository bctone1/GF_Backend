# models/partner/catalog.py
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from models.base import Base


# ========= partner.model_catalog =========
class ModelCatalog(Base):
    """
    파트너/Org에서 사용할 수 있는 모델 카탈로그.
    실제 사용 단위는 '강의실(Class)'에서 primary_model_id로 선택해서 쓴다.
    """
    __tablename__ = "model_catalog"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 예: openai, anthropic, google, lg 등
    provider = Column(Text, nullable=False)

    # 예: gpt-4o-mini, gemini-2.5-flash, exaone-4.1
    model_name = Column(Text, nullable=False)

    # chat | embedding | stt | image | tts | rerank
    modality = Column(Text, nullable=False, server_default=text("'chat'"))

    # 병렬 비교 실습 지원 여부 (chat 계열에서만 의미 있음)
    supports_parallel = Column(Boolean, nullable=False, server_default=text("false"))

    # 기본 과금 정보 (토큰/분당/호출당 등 JSON 형태)
    default_pricing = Column(JSONB)

    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 이 모델을 primary_model 로 쓰는 "강의실(Class)"들
    # → Class 모델 쪽에 primary_model = relationship("ModelCatalog", back_populates="primary_for_classes")
    primary_for_classes = relationship(
        "Class",
        back_populates="primary_model",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "model_name",
            name="uq_model_catalog_provider_model",
        ),
        CheckConstraint(
            "modality IN ('chat','embedding','stt','image','tts','rerank')",
            name="chk_model_catalog_modality",
        ),
        CheckConstraint(
            "default_pricing IS NULL OR jsonb_typeof(default_pricing) = 'object'",
            name="chk_model_catalog_pricing_obj",
        ),
        Index(
            "idx_model_catalog_provider_modality",
            "provider",
            "modality",
        ),
        Index(
            "idx_model_catalog_active",
            "is_active",
        ),
        {"schema": "partner"},
    )


# ========= partner.provider_credentials =========
class ProviderCredential(Base):
    """
    Org 단위 LLM Provider 자격 증명.
    - org_id 기준으로 관리 (Org 하나에 provider별 자격증명 1개)
    """
    __tablename__ = "provider_credentials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # FK → partner.org.id (기관 기준)
    org_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 예: openai, anthropic, google, upstage 등
    provider = Column(Text, nullable=False)

    # 키 식별용 라벨 (예: "메인 키", "연구실용 키")
    credential_label = Column(Text)

    # 암호화 저장 (원문 API 키 금지)
    api_key_encrypted = Column(Text, nullable=False)

    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_validated_at = Column(DateTime(timezone=True))

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 관계: OrgLlmSetting에서 참조
    org_settings = relationship(
        "OrgLlmSetting",
        back_populates="provider_credential",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "provider",
            name="uq_provider_credentials_org_provider",
        ),
        Index(
            "idx_provider_credentials_org_provider",
            "org_id",
            "provider",
        ),
        Index(
            "idx_provider_credentials_active",
            "is_active",
        ),
        Index(
            "idx_provider_credentials_validated",
            "last_validated_at",
        ),
        {"schema": "partner"},
    )


# ========= partner.org_llm_settings =========
class OrgLlmSetting(Base):
    """
    Org 단위 LLM 기본 설정.
    - 어떤 모델을 기본 채팅 모델로 쓸지
    - 병렬 모드 허용 여부
    - 메시지/토큰 한도 등
    """
    __tablename__ = "org_llm_settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # FK → partner.org.id
    org_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 기본 채팅 모델명 (예: gpt-4o-mini)
    # 필요하면 나중에 ModelCatalog FK로 승격 가능
    default_chat_model = Column(Text, nullable=False)

    # 병렬 비교 모드 허용 여부 (클래스/세션 레벨에서 사용할 수 있는지)
    enable_parallel_mode = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # Org 전체 일일 메시지 수 한도 (NULL = 제한 없음)
    daily_message_limit = Column(Integer)

    # 토큰 사용량 경고 임계값 (NULL = 사용 안함)
    token_alert_threshold = Column(Integer)

    # 사용할 ProviderCredential
    provider_credential_id = Column(
        BigInteger,
        ForeignKey("partner.provider_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 마지막으로 설정을 변경한 주체 ID
    # (지금은 Org 기준 FK로 두었는데, 추후 user.users.user_id 로 바꿔도 됨)
    updated_by = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="SET NULL"),
        nullable=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 관계
    provider_credential = relationship(
        "ProviderCredential",
        back_populates="org_settings",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id",
            name="uq_org_llm_settings_org",
        ),
        CheckConstraint(
            "daily_message_limit IS NULL OR daily_message_limit >= 0",
            name="chk_org_llm_daily_limit_nonneg",
        ),
        CheckConstraint(
            "token_alert_threshold IS NULL OR token_alert_threshold >= 0",
            name="chk_org_llm_token_threshold_nonneg",
        ),
        Index(
            "idx_org_llm_settings_org",
            "org_id",
        ),
        Index(
            "idx_org_llm_settings_cred",
            "provider_credential_id",
        ),
        {"schema": "partner"},
    )
