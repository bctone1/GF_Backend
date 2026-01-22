# models/user/comparison.py

from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


# =========================
# user.practice_comparison_runs
# =========================
class PracticeComparisonRun(Base):
    """
    비교 모드 실행 1번의 '헤더(그룹)'.
    결과는 practice_responses에 (comparison_run_id + panel_key)로 매핑.
    panel_a_config / panel_b_config에는 모드(llm|doc|rag), knowledge_ids, rag params 등을 스냅샷으로 저장.
    """

    __tablename__ = "practice_comparison_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 어느 practice session에서 발생했는지
    session_id = Column(
        BigInteger,
        ForeignKey("user.practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    # 공통 프롬프트 스냅샷
    prompt_text = Column(Text, nullable=False)

    # A/B 패널 설정 스냅샷
    panel_a_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    panel_b_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

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
        Index("idx_practice_comparison_runs_session_time", "session_id", "created_at"),
        {"schema": "user"},
    )
