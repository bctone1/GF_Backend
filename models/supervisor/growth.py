# models/growth.py
from sqlalchemy import (
    Column, BigInteger, String, Text, DateTime, Integer,
    ForeignKey, UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base


# ========== supervisor.growth_channels ==========
class GrowthChannel(Base):
    __tablename__ = "growth_channels"

    channel_id = Column(BigInteger, primary_key=True, autoincrement=True)
    channel_name = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("channel_name", name="uq_growth_channels_name"),
        Index("idx_growth_channels_name", "channel_name"),
        {"schema": "supervisor"},
    )


# ========== supervisor.user_acquisition ==========
class UserAcquisition(Base):
    __tablename__ = "user_acquisition"

    acquisition_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("supervisor.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    # SET NULL을 사용하려면 nullable=True여야 함(명세의 충돌 해소)
    channel_id = Column(
        BigInteger,
        ForeignKey("supervisor.growth_channels.channel_id", ondelete="SET NULL"),
        nullable=True,
    )

    acquired_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    campaign_info = Column(JSONB, nullable=True)

    __table_args__ = (
        # 같은 유저-채널 복수 기록 방지(캠페인 단위 중복 허용 시 제거)
        UniqueConstraint("user_id", "channel_id", name="uq_user_acquisition_user_channel"),
        Index("idx_user_acquisition_user_time", "user_id", "acquired_at"),
        Index("idx_user_acquisition_channel_time", "channel_id", "acquired_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.feedback ==========
class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("supervisor.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
    )

    category = Column(String(64), nullable=True)  # ui, performance, billing 등 임의 카테고리
    rating = Column(Integer, nullable=True)       # 1~5
    comment = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating BETWEEN 1 AND 5)", name="chk_feedback_rating_1_5"),
        # 세션당 1회 정책을 쓰려면 session_id 추가 후 (session_id) UNIQUE 권장.
        # 현재는 사용자-조직-카테고리 중복 방지(운영 정책에 맞게 조정)
        UniqueConstraint("user_id", "organization_id", "category", name="uq_feedback_user_org_category_once"),
        Index("idx_feedback_user_time", "user_id", "submitted_at"),
        Index("idx_feedback_org_time", "organization_id", "submitted_at"),
        Index("idx_feedback_rating_time", "rating", "submitted_at"),
        {"schema": "supervisor"},
    )
