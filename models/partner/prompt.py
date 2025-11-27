# models/partner/prompt.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, Integer, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========= partner.prompt_templates =========
class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # scope='global'이면 NULL, scope='partner'면 NOT NULL
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=True,
    )

    name = Column(Text, nullable=False)
    description = Column(Text)
    scope = Column(Text, nullable=False, server_default=text("'partner'"))  # 'partner' | 'global'
    created_by = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 관계
    versions = relationship(
        "PromptTemplateVersion",
        back_populates="template",
        passive_deletes=True,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # 파트너 내 이름 유일. 글로벌(NULL)은 중복 허용.
        UniqueConstraint("partner_id", "name", name="uq_prompt_templates_partner_name"),
        CheckConstraint("scope IN ('partner','global')", name="chk_prompt_templates_scope"),
        CheckConstraint(
            "(scope = 'global' AND partner_id IS NULL) OR (scope = 'partner' AND partner_id IS NOT NULL)",
            name="chk_prompt_templates_scope_partner_rule",
        ),
        Index("idx_prompt_templates_partner_name", "partner_id", "name"),
        Index("idx_prompt_templates_is_archived", "is_archived"),
        {"schema": "partner"},
    )


# ========= partner.prompt_template_versions =========
class PromptTemplateVersion(Base):
    __tablename__ = "prompt_template_versions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    template_id = Column(
        BigInteger,
        ForeignKey("partner.prompt_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    meta = Column("metadata", JSONB)

    created_by = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 관계
    template = relationship("PromptTemplate", back_populates="versions", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_prompt_template_versions_template_version"),
        Index("idx_prompt_template_versions_template", "template_id"),
        {"schema": "partner"},
    )


# ========= partner.prompt_bindings =========
class PromptBinding(Base):
    __tablename__ = "prompt_bindings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    template_version_id = Column(
        BigInteger,
        ForeignKey("partner.prompt_template_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 프로젝트 → 분반(class)로 전환
    scope_type = Column(Text, nullable=False)   # 'class' | 'global'
    scope_id = Column(BigInteger, nullable=True)  # global이면 NULL, class면 NOT NULL
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 관계
    template_version = relationship("PromptTemplateVersion", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("scope_type IN ('class','global')", name="chk_prompt_bindings_scope_type"),
        CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'class' AND scope_id IS NOT NULL)",
            name="chk_prompt_bindings_scope_rule",
        ),
        UniqueConstraint("scope_type", "scope_id", "template_version_id", name="uq_prompt_bindings_scope_version"),
        Index("idx_prompt_bindings_scope", "scope_type", "scope_id"),
        Index("idx_prompt_bindings_active", "is_active"),
        Index("idx_prompt_bindings_version", "template_version_id"),
        {"schema": "partner"},
    )
