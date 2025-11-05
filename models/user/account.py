# models/user/account.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime, BigInteger, UniqueConstraint,
    ForeignKey, Index, CheckConstraint, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.orm import relationship
from models.base import Base


# ========== user.users ==========
class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(CITEXT, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'active'"))
    default_role = Column(Text, nullable=False, server_default=text("'member'"))
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("UserProfile", back_populates="user", uselist=False, passive_deletes=True)
    security = relationship("UserSecuritySetting", back_populates="user", uselist=False, passive_deletes=True)

    __table_args__ = (
        Index("idx_users_status_created", "status", "created_at"),
        {"schema": "user"},
    )


# ========== user.user_profiles ==========
class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    full_name = Column(Text, nullable=True)
    job_title = Column(Text, nullable=True)
    department = Column(Text, nullable=True)
    phone_number = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    avatar_initials = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profile", passive_deletes=True)

    __table_args__ = (
        {"schema": "user"},
    )


# ========== user.user_security_settings ==========
class UserSecuritySetting(Base):
    __tablename__ = "user_security_settings"

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    two_factor_enabled = Column(Boolean, nullable=False, server_default=text("false"))
    two_factor_method = Column(Text, nullable=True)  # totp | sms | email
    backup_codes = Column(JSONB, nullable=True)
    last_password_change_at = Column(DateTime(timezone=True), nullable=True)
    recovery_email = Column(CITEXT, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="security", passive_deletes=True)

    __table_args__ = (
        {"schema": "user"},
    )


# ========== user.user_login_sessions ==========
class UserLoginSession(Base):
    __tablename__ = "user_login_sessions"

    session_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    device_name = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)
    location = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)

    logged_in_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    logged_out_at = Column(DateTime(timezone=True), nullable=True)
    is_current = Column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint(
            "(logged_out_at IS NULL) OR (logged_out_at >= logged_in_at)",
            name="chk_user_login_sessions_time",
        ),
        Index("idx_user_login_sessions_user_time", "user_id", "logged_in_at"),
        Index("idx_user_login_sessions_current", "user_id", "is_current"),
        {"schema": "user"},
    )


# ========== user.user_privacy_settings ==========
class UserPrivacySetting(Base):
    __tablename__ = "user_privacy_settings"

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    save_conversation_history = Column(Boolean, nullable=False, server_default=text("true"))
    allow_data_collection = Column(Boolean, nullable=False, server_default=text("true"))
    allow_personalized_ai = Column(Boolean, nullable=False, server_default=text("true"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        {"schema": "user"},
    )
