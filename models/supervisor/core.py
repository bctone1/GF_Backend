# models/supervisor/core.py
from sqlalchemy import (
    Column, BigInteger, String, Integer, DateTime, Boolean, Numeric, Text, Date,
    ForeignKey, UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB, CITEXT, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from models.base import Base

# =========================
# users
# =========================
class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    email = Column(CITEXT, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, server_default=text("'active'"))
    last_active_at = Column(DateTime(timezone=True))
    signup_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    session_avg_duration = Column(Integer)
    total_usage = Column(BigInteger, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="users")
    sessions = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    role_assignments = relationship(
        "UserRoleAssignment", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_org_id", "organization_id"),
        Index("ix_users_status", "status"),
        Index("ix_users_signup_at", "signup_at"),
        {"schema": "supervisor"},
    )


# =========================
# user_roles
# =========================
class UserRole(Base):
    __tablename__ = "user_roles"

    role_id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_name = Column(String(64), nullable=False)
    permissions_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    assignments = relationship(
        "UserRoleAssignment", back_populates="role", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("role_name", name="uq_user_roles_name"),
        {"schema": "supervisor"},
    )


# =========================
# user_role_assignments
# =========================
class UserRoleAssignment(Base):
    __tablename__ = "user_role_assignments"

    assignment_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("supervisor.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id = Column(
        BigInteger,
        ForeignKey("supervisor.user_roles.role_id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    assigned_by = Column(BigInteger)

    user = relationship("User", back_populates="role_assignments")
    role = relationship("UserRole", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role_once"),
        Index("ix_user_role_assignments_user", "user_id", "assigned_at"),
        Index("ix_user_role_assignments_role", "role_id"),
        {"schema": "supervisor"},
    )


# =========================
# sessions
# =========================
class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("supervisor.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True))
    duration_sec = Column(Integer)
    device_info = Column(JSONB)
    ip_address = Column(INET)

    user = relationship("User", back_populates="sessions")
    organization = relationship("Organization")

    __table_args__ = (
        CheckConstraint("duration_sec IS NULL OR duration_sec >= 0", name="chk_sessions_duration_nonneg"),
        Index("ix_sessions_user_started", "user_id", "started_at"),
        Index("ix_sessions_org_started", "organization_id", "started_at"),
        {"schema": "supervisor"},
    )


# =========================
# organizations
# =========================
class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    plan_id = Column(
        BigInteger,
        ForeignKey("supervisor.plans.plan_id", ondelete="SET NULL"),
        nullable=True,
    )
    industry = Column(String(64))
    company_size = Column(String(32))
    status = Column(String(32), nullable=False, server_default=text("'active'"))
    joined_at = Column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    trial_end_at = Column(Date)
    mrr = Column(Numeric(12, 2), nullable=False, server_default=text("0"))
    notes = Column(Text)
    created_by = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    plan = relationship("Plan", back_populates="organizations")
    users = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("status IN ('active','trial','suspended')", name="chk_organizations_status"),
        Index("ix_organizations_plan_id", "plan_id"),
        Index("ix_organizations_status", "status"),
        Index("ix_organizations_joined_at", "joined_at"),
        {"schema": "supervisor"},
    )



# =========================
# plans (추후 삭제 가능성 있는 기능)
# =========================
class Plan(Base):
    __tablename__ = "plans"

    plan_id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_name = Column(String(64), nullable=False)
    billing_cycle = Column(String(32), nullable=False, server_default=text("'monthly'"))
    price_mrr = Column(Numeric(12, 2), nullable=False, server_default=text("0"))
    price_arr = Column(Numeric(12, 2), nullable=False, server_default=text("0"))
    features_json = Column(JSONB)
    max_users = Column(Integer)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    organizations = relationship(
        "Organization", back_populates="plan", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("plan_name", name="uq_plans_name"),
        {"schema": "supervisor"},
    )
