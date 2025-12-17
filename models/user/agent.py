# models/user/agent.py
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    Integer,
    DateTime,
    Numeric,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
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

    name = Column(Text, nullable=False)
    role_description = Column(Text, nullable=True)

    # 프롬프트 버전/롤백 없이 "현재 프롬프트 1개"만 유지
    system_prompt = Column(Text, nullable=False)

    # draft/archived 같은 상태를 안 쓰기로 했으니 단순 boolean
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    # 내가 만든건지 강사껀지 확인용
    template_source = Column(Text, nullable=True)

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

    examples = relationship(
        "AgentExample",
        back_populates="agent",
        passive_deletes=True,
    )
    usage_stat = relationship(
        "AgentUsageStat",
        back_populates="agent",
        uselist=False,
        passive_deletes=True,
    )
    shares = relationship(
        "AgentShare",
        back_populates="agent",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_ai_agents_owner_active", "owner_id", "is_active"),
        Index("idx_ai_agents_owner_created_at", "owner_id", "created_at"),
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
    example_type = Column(
        Text,
        nullable=False,
        server_default=text("'few_shot'"),
    )  # few_shot|tool|note 등
    input_text = Column(Text, nullable=True)
    output_text = Column(Text, nullable=True)
    position = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent = relationship("AIAgent", back_populates="examples", passive_deletes=True)

    __table_args__ = (
        CheckConstraint(
            "position IS NULL OR position >= 0",
            name="chk_agent_examples_position_nonneg",
        ),
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
    avg_rating = Column(Numeric(3, 2), nullable=True)  # 0.00~5.00 권장
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
    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 실제 공유를 수행한 유저 (감사용)
    shared_by_user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent = relationship("AIAgent", back_populates="shares", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("agent_id", "class_id", name="uq_agent_shares_agent_class"),
        Index("idx_agent_shares_agent", "agent_id"),
        Index("idx_agent_shares_class", "class_id"),
        {"schema": "user"},
    )
