# models/user/comparison.py
from __future__ import annotations

from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    Integer,
    String,
    Numeric,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


# =========================
# user.practice_comparison_runs  (v2: panel 단일 실행 로그)
# =========================
class PracticeComparisonRun(Base):
    """
    비교 모드의 '패널 1회 실행' 레코드
    실행 버튼이 A/B 각각이므로, 한 row가 panel(a|b) 하나만 가짐
    결과는 practice_responses에 comparison_run_id(+optional panel_key)로 매핑 가능
    """

    __tablename__ = "practice_comparison_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(
        BigInteger,
        ForeignKey("user.practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    # panel: 'a' or 'b'
    panel = Column(String(1), nullable=False)
    prompt_text = Column(Text, nullable=False)
    model_names = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # mode: llm | doc | rag
    mode = Column(String(10), nullable=False)

    knowledge_ids = Column(JSONB, nullable=True, server_default=text("'[]'::jsonb"))

    top_k = Column(Integer, nullable=True)
    chunk_size = Column(Integer, nullable=True)
    threshold = Column(Numeric(10, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship(
        "PracticeSession",
        back_populates="comparison_runs",
        passive_deletes=True,
    )

    responses = relationship(
        "PracticeResponse",
        back_populates="comparison_run",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("length(prompt_text) > 0", name="chk_practice_comparison_runs_prompt_nonempty"),
        CheckConstraint("panel in ('a','b')", name="chk_practice_comparison_runs_panel"),
        CheckConstraint("mode in ('llm','doc','rag')", name="chk_practice_comparison_runs_mode"),
        Index("idx_practice_comparison_runs_session_panel_time", "session_id", "panel", "created_at"),
        {"schema": "user"},
    )
