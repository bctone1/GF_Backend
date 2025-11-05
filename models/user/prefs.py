# models/user/prefs.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base


# ========== user.user_preferences ==========
class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    preferences = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        {"schema": "user"},
    )


# ========== user.user_preference_history ==========
class UserPreferenceHistory(Base):
    __tablename__ = "user_preference_history"

    history_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    preferences = Column(JSONB, nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_user_preference_history_user_time", "user_id", "changed_at"),
        {"schema": "user"},
    )


# ========== user.user_notification_preferences ==========
class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"

    preference_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    channel = Column(Text, nullable=False)      # email | sms | push 등
    event_type = Column(Text, nullable=False)   # e.g. 'system_notice','deadline','api_cost_alert'
    is_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "channel", "event_type", name="uq_user_notif_pref_user_channel_event"),
        Index("idx_user_notif_pref_user", "user_id"),
        Index("idx_user_notif_pref_channel_event", "channel", "event_type"),
        {"schema": "user"},
    )


# ========== user.notification_events ==========
class NotificationEvent(Base):
    __tablename__ = "notification_events"

    event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    channel = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False)       # queued | sent | failed 등
    payload = Column(JSONB, nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_notification_events_user_time", "user_id", "created_at"),
        Index("idx_notification_events_channel_event_time", "channel", "event_type", "created_at"),
        Index("idx_notification_events_status_time", "status", "created_at"),
        {"schema": "user"},
    )
