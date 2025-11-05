# models/partner/prompt.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, Integer, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base


# ========= partner.prompt_templates =========
class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=True,  # 전역 템플릿 허용 시 NULL
    )

    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(Text, nullable=False, server_default=text("'partner'"))  # 'partner' 등
    created_by = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_archived = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
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
    metadata = Column(JSONB, nullable=True)
    created_by = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

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

    scope_type = Column(Text, nullable=False)  # 'project' | 'global'
    scope_id = Column(BigInteger, nullable=True)  # global이면 NULL, project면 NOT NULL
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("scope_type IN ('project','global')", name="chk_prompt_bindings_scope_type"),
        CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'project' AND scope_id IS NOT NULL)",
            name="chk_prompt_bindings_scope_rule",
        ),
        # 바인딩 유니크(스펙 상 템플릿 기준이었으나, 실제 컬럼은 version ID이므로 이에 맞춰 적용)
        UniqueConstraint("scope_type", "scope_id", "template_version_id", name="uq_prompt_bindings_scope_version"),
        Index("idx_prompt_bindings_scope", "scope_type", "scope_id"),
        Index("idx_prompt_bindings_active", "is_active"),
        {"schema": "partner"},
    )
