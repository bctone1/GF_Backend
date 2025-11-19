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
# supervisor.supervisors
# =========================
class SupervisorUser(Base):
    __tablename__ = "supervisors"

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

    organization = relationship("Organization", back_populates="supervisors")
    sessions = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    role_assignments = relationship(
        "UserRoleAssignment", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_supervisors_email"),
        Index("ix_supervisors_org_id", "organization_id"),
        Index("ix_supervisors_status", "status"),
        Index("ix_supervisors_signup_at", "signup_at"),
        {"schema": "supervisor"},
    )

# =========================
# partner_promotion_requests
# =========================
class PartnerPromotionRequest(Base):
    """
    user가 '파트너/강사로 승격 요청'을 올린 큐
    - user 쪽에서 생성 (요청)
    - supervisor가 교육파트너 관리 화면에서 승인/거절
    - 승인될 때 기존 promote_user_to_partner 로직 호출
    """

    __tablename__ = "partner_promotion_requests"

    request_id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 요청한 user
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    # 편의상 이메일 / 이름도 같이 스냅샷으로 저장
    email = Column(CITEXT, nullable=True)
    full_name = Column(Text, nullable=True)

    # 소속 기관명(org) - 폼에서 입력한 기관 이름 자체
    requested_org_name = Column(String(255), nullable=False)

    # 승인 시 부여할 파트너 역할 (예: partner_admin, instructor)
    target_role = Column(String(64), nullable=False, server_default=text("'partner_admin'"))

    # 상태: pending / approved / rejected / cancelled
    status = Column(String(32), nullable=False, server_default=text("'pending'"))

    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at = Column(DateTime(timezone=True))
    decided_reason = Column(Text)  # 승인/거절 사유

    # 승인 후 실제로 생성/연결된 partner / partner_user
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="SET NULL"),
        nullable=True,
    )
    partner_user_id = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 추가 정보 (전화번호, 교육 분야, 유입경로 등)
    meta = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="chk_partner_promotion_status",
        ),
        Index("ix_partner_promo_status_req", "status", "requested_at"),
        Index("ix_partner_promo_user", "user_id", "requested_at"),
        Index(
            "ux_partner_promo_pending_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
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
        ForeignKey("supervisor.supervisors.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id = Column(
        BigInteger,
        ForeignKey("supervisor.user_roles.role_id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    assigned_by = Column(BigInteger)

    user = relationship("SupervisorUser", back_populates="role_assignments")
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
        ForeignKey("supervisor.supervisors.user_id", ondelete="CASCADE"),
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

    user = relationship("SupervisorUser", back_populates="sessions")
    organization = relationship("Organization", back_populates="sessions")

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
    supervisors = relationship(
        "SupervisorUser", back_populates="organization", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions = relationship(  # ← 추가
        "Session", back_populates="organization", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("status IN ('active','trial','suspended')", name="chk_organizations_status"),
        Index("ix_organizations_plan_id", "plan_id"),
        Index("ix_organizations_status", "status"),
        Index("ix_organizations_joined_at", "joined_at"),
        {"schema": "supervisor"},
    )


# =========================
# plans
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
