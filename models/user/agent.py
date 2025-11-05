# models/user/agent.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, DateTime, Numeric, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========== user.ai_agents ==========
class AIAgent(Base):
    __tablename__ = "ai_agents"

    agent_id = Column(BigInteger, primary_key=True, autoincrement=True)

    owner_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    # 선택 참조
    project_id = Column(
        BigInteger,
        ForeignKey("user.projects.project_id", ondelete="SET NULL"),
        nullable=True,
    )
    document_id = Column(
        BigInteger,
        ForeignKey("user.documents.document_id", ondelete="SET NULL"),
        nullable=True,
    )

    name = Column(Text, nullable=False)
    role_description = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'draft'"))
    icon = Column(Text, nullable=True)
    template_source = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    prompts = relationship("AgentPrompt", back_populates="agent", passive_deletes=True)
    examples = relationship("AgentExample", back_populates="agent", passive_deletes=True)
    usage_stat = relationship("AgentUsageStat", back_populates="agent", uselist=False, passive_deletes=True)

    __table_args__ = (
        Index("idx_ai_agents_owner_status", "owner_id", "status"),
        Index("idx_ai_agents_project", "project_id"),
        Index("idx_ai_agents_document", "document_id"),
        {"schema": "user"},
    )


# ========== user.agent_prompts ==========
class AgentPrompt(Base):
    __tablename__ = "agent_prompts"

    prompt_id = Column(BigInteger, primary_key=True, autoincrement=True)

    agent_id = Column(
        BigInteger,
        ForeignKey("user.ai_agents.agent_id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(Integer, nullable=False)
    system_prompt = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("false"))

    agent = relationship("AIAgent", back_populates="prompts", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_prompts_agent_version"),
        # 활성 버전 단일성(부분 유니크)
        Index(
            "uq_agent_prompts_active_once",
            "agent_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index("idx_agent_prompts_agent", "agent_id"),
        {"schema": "user"},
    )


# ========== user.agent_examples ==========
class AgentExample(Base):
    __tablename__ = "agent_examples"

    example_id = Column(BigInteger, primary_key=True, autoincrement=True)

    agent_id = Column(
        BigInteger,
        ForeignKey("user.ai_agents.agent_id", ondelete="CASCADE"),
        nullable=False,
    )
    example_type = Column(Text, nullable=False, server_default=text("'few_shot'"))  # few_shot|tool|note 등
    input_text = Column(Text, nullable=True)
    output_text = Column(Text, nullable=True)
    position = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent = relationship("AIAgent", back_populates="examples", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("position IS NULL OR position >= 0", name="chk_agent_examples_position_nonneg"),
        Index("idx_agent_examples_agent_pos", "agent_id", "position"),
        {"schema": "user"},
    )


# ========== user.agent_usage_stats ==========
class AgentUsageStat(Base):
    __tablename__ = "agent_usage_stats"

    usage_stat_id = Column(BigInteger, primary_key=True, autoincrement=True)

    agent_id = Column(
        BigInteger,
        ForeignKey("user.ai_agents.agent_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    usage_count = Column(Integer, nullable=False, server_default=text("0"))
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    avg_rating = Column(Numeric(3, 2), nullable=True)      # 0.00~5.00 권장
    total_tokens = Column(BigInteger, nullable=False, server_default=text("0"))

    agent = relationship("AIAgent", back_populates="usage_stat", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("usage_count >= 0", name="chk_agent_usage_stats_count_nonneg"),
        CheckConstraint("total_tokens >= 0", name="chk_agent_usage_stats_tokens_nonneg"),
        CheckConstraint(
            "avg_rating IS NULL OR (avg_rating >= 0 AND avg_rating <= 5)",
            name="chk_agent_usage_stats_rating_range",
        ),
        Index("idx_agent_usage_stats_last_used", "last_used_at"),
        {"schema": "user"},
    )
