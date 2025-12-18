# models/user/practice.py
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from models.base import Base


# ========== user.practice_sessions ==========
class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    session_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="SET NULL"),
        nullable=True,
    )

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

    # Agent 템플릿 연결
    agent_id = Column(
        BigInteger,
        ForeignKey("user.ai_agents.agent_id", ondelete="SET NULL"),
        nullable=True,
    )

    title = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    models = relationship(
        "PracticeSessionModel",
        back_populates="session",
        passive_deletes=True,
    )
    responses = relationship(
        "PracticeResponse",
        back_populates="session",
        passive_deletes=True,
    )
    settings = relationship(
        "PracticeSessionSetting",
        back_populates="session",
        uselist=False,
        passive_deletes=True,
    )

    project = relationship(
        "UserProject",
        back_populates="sessions",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_practice_sessions_user", "user_id"),
        Index("idx_practice_sessions_knowledge", "knowledge_id"),
        Index("idx_practice_sessions_agent", "agent_id"),
        {"schema": "user"},
    )


# ========== user.practice_session_settings ==========
class PracticeSessionSetting(Base):
    __tablename__ = "practice_session_settings"

    setting_id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(
        BigInteger,
        ForeignKey("user.practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    style_preset = Column(Text, nullable=True)

    style_params = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    generation_params = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # Agent 스냅샷(세션 시작 시점의 agent 상태를 고정해서 재현성 확보)
    agent_snapshot = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    session = relationship(
        "PracticeSession",
        back_populates="settings",
        passive_deletes=True,
    )

    few_shot_links = relationship(
        "PracticeSessionSettingFewShot",
        back_populates="setting",
        passive_deletes=True,
        order_by="PracticeSessionSettingFewShot.sort_order",
    )

    __table_args__ = (
        Index("idx_practice_session_settings_session", "session_id"),
        {"schema": "user"},
    )


# ========== user.few_shot_examples (개인 라이브러리) ==========
class UserFewShotExample(Base):
    __tablename__ = "few_shot_examples"

    example_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    title = Column(Text, nullable=True)

    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=False)

    meta = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    setting_links = relationship(
        "PracticeSessionSettingFewShot",
        back_populates="example",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_few_shot_examples_user", "user_id"),
        {"schema": "user"},
    )


# ========== user.practice_session_setting_few_shots (매핑) ==========
class PracticeSessionSettingFewShot(Base):
    __tablename__ = "practice_session_setting_few_shots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    setting_id = Column(
        BigInteger,
        ForeignKey("user.practice_session_settings.setting_id", ondelete="CASCADE"),
        nullable=False,
    )

    example_id = Column(
        BigInteger,
        ForeignKey("user.few_shot_examples.example_id", ondelete="CASCADE"),
        nullable=False,
    )

    sort_order = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    setting = relationship(
        "PracticeSessionSetting",
        back_populates="few_shot_links",
        passive_deletes=True,
    )

    example = relationship(
        "UserFewShotExample",
        back_populates="setting_links",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("setting_id", "example_id", name="uq_setting_example"),
        Index("idx_setting_few_shots_setting", "setting_id"),
        Index("idx_setting_few_shots_example", "example_id"),
        {"schema": "user"},
    )


# ========== user.practice_session_models ==========
class PracticeSessionModel(Base):
    __tablename__ = "practice_session_models"

    session_model_id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(
        BigInteger,
        ForeignKey("user.practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    model_name = Column(Text, nullable=False)
    is_primary = Column(Boolean, nullable=False, server_default=text("false"))

    generation_params = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship(
        "PracticeSession",
        back_populates="models",
        passive_deletes=True,
    )

    responses = relationship(
        "PracticeResponse",
        back_populates="session_model",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_practice_session_models_session", "session_id"),
        {"schema": "user"},
    )


# ========== user.practice_responses ==========
class PracticeResponse(Base):
    __tablename__ = "practice_responses"

    response_id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_model_id = Column(
        BigInteger,
        ForeignKey("user.practice_session_models.session_model_id", ondelete="CASCADE"),
        nullable=False,
    )

    session_id = Column(
        BigInteger,
        ForeignKey("user.practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    model_name = Column(Text, nullable=False)
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)

    token_usage = Column(JSONB, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session_model = relationship(
        "PracticeSessionModel",
        back_populates="responses",
        passive_deletes=True,
    )

    session = relationship(
        "PracticeSession",
        back_populates="responses",
        passive_deletes=True,
    )

    __table_args__ = ({"schema": "user"},)
