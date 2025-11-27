# models/partner/session.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, DateTime, Numeric,
    ForeignKey, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from models.base import Base


# ========== partner.ai_sessions ==========
class AiSession(Base):
    __tablename__ = "ai_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    student_id = Column(
        BigInteger,
        ForeignKey("partner.students.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 분반 컨텍스트(선택사항, 널 허용)
    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="SET NULL"),
        nullable=True,
    )

    mode = Column(Text, nullable=False)                    # 'single' | 'parallel'
    model_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'active'"))  # active|completed|canceled|error

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    total_messages = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens = Column(Integer, nullable=False, server_default=text("0"))
    total_cost = Column(Numeric(14, 4), nullable=False, server_default=text("0"))

    # 세션을 시작한 파트너(강사) id - partners.id 참조
    initiated_by = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="SET NULL"),
        nullable=True,
    )

    messages = relationship(
        "SessionMessage",
        back_populates="session",
        passive_deletes=True,
        cascade="all, delete-orphan",
        order_by="SessionMessage.created_at",
    )

    __table_args__ = (
        CheckConstraint("mode IN ('single','parallel')", name="chk_ai_sessions_mode"),
        CheckConstraint("status IN ('active','completed','canceled','error')", name="chk_ai_sessions_status"),
        CheckConstraint("(ended_at IS NULL) OR (ended_at >= started_at)", name="chk_ai_sessions_time"),
        CheckConstraint("total_messages >= 0", name="chk_ai_sessions_msgs_nonneg"),
        CheckConstraint("total_tokens   >= 0", name="chk_ai_sessions_tokens_nonneg"),
        CheckConstraint("total_cost     >= 0", name="chk_ai_sessions_cost_nonneg"),
        Index("idx_ai_sessions_status", "status"),
        Index("idx_ai_sessions_mode", "mode"),
        Index("idx_ai_sessions_student", "student_id"),
        Index("idx_ai_sessions_class", "class_id"),
        Index("idx_ai_sessions_started", "started_at"),
        {"schema": "partner"},
    )


# ========== partner.session_messages ==========
class SessionMessage(Base):
    __tablename__ = "session_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    session_id = Column(
        BigInteger,
        ForeignKey("partner.ai_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # sender_type: 세션 참여 주체
    # - 'student' : 학생
    # - 'partner' : 파트너(강사/조교 등)
    # - 'system'  : 시스템/자동 메시지
    sender_type = Column(Text, nullable=False)  # 'student' | 'partner' | 'system'
    sender_id = Column(BigInteger, nullable=True)  # 참조 없음(옵션)

    message_type = Column(Text, nullable=False, server_default=text("'text'"))  # text|image|audio|file|tool
    content = Column(Text, nullable=False)

    tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    meta = Column(JSONB, nullable=True)  # 추가 메타(툴콜, 파일정보 등)

    # pgvector(1536)
    content_vector = Column(Vector(1536), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("AiSession", back_populates="messages", passive_deletes=True)

    __table_args__ = (
        CheckConstraint(
            "sender_type IN ('student','partner','system')",
            name="chk_session_messages_sender",
        ),
        CheckConstraint(
            "message_type IN ('text','image','audio','file','tool')",
            name="chk_session_messages_type",
        ),
        CheckConstraint(
            "tokens IS NULL OR tokens >= 0",
            name="chk_session_messages_tokens_nonneg",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="chk_session_messages_latency_nonneg",
        ),
        Index("idx_session_messages_session_time", "session_id", "created_at"),
        Index("idx_session_messages_type_time", "message_type", "created_at"),
        Index("idx_session_messages_sender", "sender_type", "sender_id"),
        # 벡터 근사검색 인덱스(코사인). pgvector 확장 필요.
        Index(
            "idx_session_messages_vec_ivfflat",
            "content_vector",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"content_vector": "vector_cosine_ops"},
        ),
        {"schema": "partner"},
    )
