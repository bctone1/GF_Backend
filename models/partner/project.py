# models/partner/project.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, Integer, Date, DateTime, Numeric, Interval,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========== partner.projects ==========
class Project(Base):
    __tablename__ = "projects"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )

    name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'planning'"))
    contract_amount = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    expected_student_count = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)

    created_by = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    settings = relationship("ProjectSetting", uselist=False, back_populates="project", passive_deletes=True)
    staff = relationship("ProjectStaff", back_populates="project", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("contract_amount >= 0", name="chk_projects_contract_nonneg"),
        CheckConstraint(
            "(start_date IS NULL OR end_date IS NULL) OR (end_date >= start_date)",
            name="chk_projects_date_range",
        ),
        Index("idx_projects_partner_status", "partner_id", "status"),
        Index("idx_projects_partner_name", "partner_id", "name"),
        {"schema": "partner"},
    )


# ========== partner.project_settings ==========
class ProjectSetting(Base):
    __tablename__ = "project_settings"

    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    auto_approve_students = Column(Boolean, nullable=False, server_default=text("false"))
    allow_self_registration = Column(Boolean, nullable=False, server_default=text("true"))
    default_project_duration = Column(Interval, nullable=True)
    auto_prune_inactive = Column(Boolean, nullable=False, server_default=text("false"))
    inactive_days_threshold = Column(Integer, nullable=True, server_default=text("60"))

    updated_by = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project = relationship("Project", back_populates="settings", passive_deletes=True)

    __table_args__ = (
        CheckConstraint(
            "inactive_days_threshold IS NULL OR inactive_days_threshold >= 0",
            name="chk_project_settings_inactive_days_nonneg",
        ),
        {"schema": "partner"},
    )


# ========== partner.project_staff ==========
class ProjectStaff(Base):
    __tablename__ = "project_staff"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    partner_user_id = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    role = Column(Text, nullable=False)
    invited_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    joined_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="staff", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("project_id", "partner_user_id", name="uq_project_staff_member_once"),
        Index("idx_project_staff_project", "project_id"),
        Index("idx_project_staff_user", "partner_user_id"),
        {"schema": "partner"},
    )
