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
    knowledge_id = Column(
        BigInteger,
        ForeignKey("user.documents.knowledge_id", ondelete="SET NULL"),
        nullable=True,
    )

    name = Column(Text, nullable=False)
    role_description = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'draft'"))
    template_source = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    prompts = relationship("AgentPrompt", back_populates="agent", passive_deletes=True)
    examples = relationship("AgentExample", back_populates="agent", passive_deletes=True)
    usage_stat = relationship("AgentUsageStat", back_populates="agent", uselist=False, passive_deletes=True)
    # class 단위 공유 관계
    shares = relationship("AgentShare", back_populates="agent", passive_deletes=True)

    __table_args__ = (
        Index("idx_ai_agents_owner_status", "owner_id", "status"),
        Index("idx_ai_agents_project", "project_id"),
        Index("idx_ai_agents_document", "knowledge_id"),
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


# ========== user.agent_shares ==========
class AgentShare(Base):
    """
    강사의 개인 에이전트를 특정 class 에 공유하는 매핑 테이블.
    - 하나의 agent 를 여러 class 에 공유 가능
    - 같은 agent_id + class_id 는 한 번만(유니크)
    """

    __tablename__ = "agent_shares"

    share_id = Column(BigInteger, primary_key=True, autoincrement=True)

    agent_id = Column(
        BigInteger,
        ForeignKey("user.ai_agents.agent_id", ondelete="CASCADE"),
        nullable=False,
    )
    # 이 에이전트를 공유하는 대상 강의실
    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 실제 공유를 수행한 유저 (일반적으로 agent.owner_id 와 동일, 감사용)
    shared_by_user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent = relationship("AIAgent", back_populates="shares", passive_deletes=True)
    # shared_by / class 에 대한 relationship 은 필요 시 다른 파일에서 추가해도 됨

    __table_args__ = (
        # 같은 agent 를 같은 class 에 중복 공유하지 않도록
        UniqueConstraint("agent_id", "class_id", name="uq_agent_shares_agent_class"),
        Index("idx_agent_shares_agent", "agent_id"),
        Index("idx_agent_shares_class", "class_id"),
        {"schema": "user"},
    )
