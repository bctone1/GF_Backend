# models/partner/activity.py
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class ActivityEvent(Base):
    """파트너 대시보드 활동 피드용 이벤트 로그."""

    __tablename__ = "activity_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Org 기준 (UsageEvent.partner_id 와 동일 기준)
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )

    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="SET NULL"),
        nullable=True,
    )

    student_id = Column(
        BigInteger,
        ForeignKey("partner.students.id", ondelete="SET NULL"),
        nullable=True,
    )

    # student_joined | budget_alert | conversation_milestone | class_started | class_ended
    event_type = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=False, server_default="'{}'::jsonb")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_activity_events_partner_created", "partner_id", "created_at"),
        Index("idx_activity_events_type_created", "event_type", "created_at"),
        {"schema": "partner"},
    )
