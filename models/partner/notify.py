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

    partner_user_id = Column(BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="CASCADE"),
        nullable=False)

    new_student_email    = Column(Boolean, nullable=False, server_default=text("true"))
    class_deadline_email = Column(Boolean, nullable=False, server_default=text("true"))  # course/class 마감 알림 기준
    settlement_email     = Column(Boolean, nullable=False, server_default=text("true"))
    api_cost_alert_email = Column(Boolean, nullable=False, server_default=text("true"))
    system_notice        = Column(Boolean, nullable=False, server_default=text("true"))
    marketing_opt_in     = Column(Boolean, nullable=False, server_default=text("false"))

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

    partner_user_id = Column(BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="CASCADE"),
        nullable=False)
    subscription_type = Column(Text, nullable=False)   # 'weekly_digest' | 'alerts' | 'marketing'
    is_subscribed     = Column(Boolean, nullable=False, server_default=text("true"))
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("partner_user_id", "subscription_type", name="uq_email_subscriptions_user_type"),
        CheckConstraint("subscription_type IN ('weekly_digest','alerts','marketing')",
                        name="chk_email_subscriptions_type"),
        Index("idx_email_subscriptions_user", "partner_user_id"),
        Index("idx_email_subscriptions_type", "subscription_type"),
        {"schema": "partner"},
    )


# ========= partner.mfa_settings =========
class MfaSetting(Base):
    __tablename__ = "mfa_settings"

    partner_user_id = Column(BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="CASCADE"),
        primary_key=True, nullable=False)

    is_enabled       = Column(Boolean, nullable=False, server_default=text("false"))
    method           = Column(Text)              # 'totp','sms','email'
    secret_encrypted = Column(Text)
    last_enabled_at  = Column(DateTime(timezone=True))
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("method IS NULL OR method IN ('totp','sms','email')",
                        name="chk_mfa_settings_method"),
        {"schema": "partner"},
    )


# ========= partner.login_activity =========
class LoginActivity(Base):
    __tablename__ = "login_activity"

    # 파티셔닝 테이블은 PK에 파티션 키를 포함해야 함
    login_at = Column(DateTime(timezone=True), primary_key=True, server_default=func.now(), nullable=False)
    id       = Column(BigInteger, primary_key=True, nullable=False)  # 부모엔 IDENTITY/serial 미적용. 파티션에서 처리 또는 애플리케이션에서 채움.

    partner_user_id = Column(BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True)
    ip_address = Column(INET)
    user_agent = Column(Text)
    status     = Column(Text, nullable=False, server_default=text("'success'"))  # success|failed

    __table_args__ = (
        CheckConstraint("status IN ('success','failed')", name="chk_login_activity_status"),
        Index("idx_login_activity_user_time", "partner_user_id", "login_at"),
        {"schema": "partner", "postgresql_partition_by": "RANGE (login_at)"},
    )
