# models/user/practice.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, DateTime, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
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

    # 이 연습 세션이 어떤 Class에 묶여 있는지 (없으면 독립 세션)
    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = Column(Text, nullable=True)

    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    models = relationship(
        "PracticeSessionModel",
        back_populates="session",
        passive_deletes=True,
    )
    comparisons = relationship(
        "ModelComparison",
        back_populates="session",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="chk_practice_sessions_time",
        ),
        Index("idx_practice_sessions_user_time", "user_id", "started_at"),
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

    session = relationship("PracticeSession", back_populates="models", passive_deletes=True)
    responses = relationship("PracticeResponse", back_populates="session_model", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("session_id", "model_name", name="uq_practice_session_models_session_model"),
        # 세션당 primary 하나만 허용(부분 유니크)
        Index(
            "uq_practice_session_models_primary_once",
            "session_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
        Index("idx_practice_session_models_session", "session_id"),
        {"schema": "user"},
    )


# ========== user.practice_responses ==========
class PracticeResponse(Base):
    __tablename__ = "practice_responses"

    response_id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_model_id = Column(  # 오타 수정: session_model_id가 정답
        BigInteger,
        ForeignKey("user.practice_session_models.session_model_id", ondelete="CASCADE"),
        nullable=False,
    )

    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    token_usage = Column(JSONB, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session_model = relationship("PracticeSessionModel", back_populates="responses", passive_deletes=True)
    ratings = relationship("PracticeRating", back_populates="response", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="chk_practice_responses_latency_nonneg"),
        Index("idx_practice_responses_model_time", "session_model_id", "created_at"),
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    response = relationship("PracticeResponse", back_populates="ratings", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("response_id", "user_id", name="uq_practice_ratings_response_user"),
        CheckConstraint("score >= 1 AND score <= 5", name="chk_practice_ratings_score_1_5"),
        Index("idx_practice_ratings_response", "response_id"),
        Index("idx_practice_ratings_user", "user_id"),
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("PracticeSession", back_populates="comparisons", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("latency_diff_ms IS NULL OR latency_diff_ms >= 0", name="chk_model_comparisons_latency_nonneg"),
        CheckConstraint("token_diff IS NULL OR token_diff >= 0", name="chk_model_comparisons_token_nonneg"),
        Index("idx_model_comparisons_session_time", "session_id", "created_at"),
        {"schema": "user"},
    )
