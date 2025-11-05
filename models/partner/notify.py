# models/partner/notify.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import INET
from models.base import Base


# ========= partner.notification_preferences =========
class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_user_id = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    new_student_email = Column(Boolean, nullable=False, server_default=text("true"))
    project_deadline_email = Column(Boolean, nullable=False, server_default=text("true"))
    settlement_email = Column(Boolean, nullable=False, server_default=text("true"))
    api_cost_alert_email = Column(Boolean, nullable=False, server_default=text("true"))
    system_notice = Column(Boolean, nullable=False, server_default=text("true"))
    marketing_opt_in = Column(Boolean, nullable=False, server_default=text("false"))

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("partner_user_id", name="uq_notification_preferences_user"),
        Index("idx_notification_preferences_user", "partner_user_id"),
        {"schema": "partner"},
    )


# ========= partner.email_subscriptions =========
class EmailSubscription(Base):
    __tablename__ = "email_subscriptions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_user_id = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subscription_type = Column(Text, nullable=False)   # 예: 'weekly_digest','alerts','marketing'
    is_subscribed = Column(Boolean, nullable=False, server_default=text("true"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("partner_user_id", "subscription_type", name="uq_email_subscriptions_user_type"),
        Index("idx_email_subscriptions_user", "partner_user_id"),
        Index("idx_email_subscriptions_type", "subscription_type"),
        {"schema": "partner"},
    )


# ========= partner.mfa_settings =========
class MfaSetting(Base):
    __tablename__ = "mfa_settings"

    partner_user_id = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    is_enabled = Column(Boolean, nullable=False, server_default=text("false"))
    method = Column(Text, nullable=True)              # 'totp','sms','email' 등
    secret_encrypted = Column(Text, nullable=True)
    last_enabled_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        {"schema": "partner"},
    )


# ========= partner.login_activity =========
class LoginActivity(Base):
    __tablename__ = "login_activity"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_user_id = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    login_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'success'"))  # 'success','failed' 등

    __table_args__ = (
        Index("idx_login_activity_user_time", "partner_user_id", "login_at"),
        Index("idx_login_activity_status_time", "status", "login_at"),
        {"schema": "partner", "postgresql_partition_by": "RANGE (login_at)"},
    )
