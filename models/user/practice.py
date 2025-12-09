# models/user/practice.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, DateTime, Boolean,
    ForeignKey, Index, text,
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

    title = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

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

    # 관계들
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

    comparisons = relationship(
        "ModelComparison",
        back_populates="session",
        passive_deletes=True,
    )

    # 프로젝트와의 관계
    project = relationship(
        "UserProject",
        back_populates="sessions",  # UserProject.sessions 가 있어야 함
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_practice_sessions_user", "user_id"),
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
    # provider 는 config.PRACTICE_MODELS 로 해석하니까 ORM에서는 제거
    is_primary = Column(Boolean, nullable=False, server_default=text("false"))

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

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
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

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

    ratings = relationship(
        "PracticeRating",
        back_populates="response",
        passive_deletes=True,
    )

    __table_args__ = (
        {"schema": "user"},
    )


# ========== user.practice_ratings ==========
class PracticeRating(Base):
    __tablename__ = "practice_ratings"

    rating_id = Column(BigInteger, primary_key=True, autoincrement=True)

    response_id = Column(
        BigInteger,
        ForeignKey("user.practice_responses.response_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    score = Column(Integer, nullable=False)
    feedback = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    response = relationship(
        "PracticeResponse",
        back_populates="ratings",
        passive_deletes=True,
    )

    __table_args__ = (
        {"schema": "user"},
    )


# ========== user.model_comparisons ==========
class ModelComparison(Base):
    __tablename__ = "model_comparisons"

    comparison_id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(
        BigInteger,
        ForeignKey("user.practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    model_a = Column(Text, nullable=False)
    model_b = Column(Text, nullable=False)
    winner_model = Column(Text, nullable=True)
    latency_diff_ms = Column(Integer, nullable=True)
    token_diff = Column(Integer, nullable=True)
    user_feedback = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session = relationship(
        "PracticeSession",
        back_populates="comparisons",
        passive_deletes=True,
    )

    __table_args__ = (
        {"schema": "user"},
    )
