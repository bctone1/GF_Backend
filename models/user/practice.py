# models/user/practice.py

from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
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

    # knowledge_ids(JSON 배열)로 통일 [1, 2, 3]
    knowledge_ids = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    # Prompt 템플릿 연결(JSON 배열) [1, 2, 3]
    prompt_ids = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    title = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

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
    comparison_runs = relationship(
        "PracticeComparisonRun",
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
        # JSONB 배열 검색(@>, ? 등) 대비 GIN 인덱스
        Index(
            "idx_practice_sessions_knowledge_ids",
            "knowledge_ids",
            postgresql_using="gin",
        ),
        Index(
            "idx_practice_sessions_prompt_ids",
            "prompt_ids",
            postgresql_using="gin",
        ),
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


    few_shot_example_ids = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    # Prompt 스냅샷(세션 시작 시점의 prompt 상태를 고정해서 재현성 확보)
    prompt_snapshot = Column(
        "agent_snapshot",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    session = relationship(
        "PracticeSession",
        back_populates="settings",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_practice_session_settings_session", "session_id"),
        # JSONB 배열 검색(@>) 대비 GIN 인덱스
        Index(
            "idx_practice_session_settings_few_shot_ids",
            "few_shot_example_ids",
            postgresql_using="gin",
        ),
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
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_few_shot_examples_user", "user_id"),
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

    comparison_run_id = Column(
        BigInteger,
        ForeignKey("user.practice_comparison_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    panel_key = Column(Text, nullable=True)

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

    comparison_run = relationship(
        "PracticeComparisonRun",
        back_populates="responses",
    )

    __table_args__ = (
        Index("idx_practice_responses_comparison_run", "comparison_run_id"),
        {"schema": "user"},
    )
