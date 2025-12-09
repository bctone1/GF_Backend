# models/user/project.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, DateTime, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from models.base import Base


# ========== user.projects ==========
class UserProject(Base):
    __tablename__ = "projects"

    project_id = Column(BigInteger, primary_key=True, autoincrement=True)

    owner_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    # NEW: 어떤 class 안의 프로젝트인지
    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="CASCADE"),  # class 삭제 시 프로젝트들도 같이 삭제
        nullable=False,
    )

    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    # 지금은 personal만 사용
    project_type = Column(Text, nullable=False, server_default=text("'personal'"))
    status = Column(Text, nullable=False, server_default=text("'active'"))

    progress_percent = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    practice_hours = Column(Numeric(10, 2), nullable=False, server_default=text("0"))
    conversation_count = Column(Integer, nullable=False, server_default=text("0"))

    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    members   = relationship("ProjectMember", back_populates="project", passive_deletes=True)
    tags      = relationship("ProjectTagAssignment", back_populates="project", passive_deletes=True)
    metrics   = relationship("ProjectMetric", back_populates="project", passive_deletes=True)
    activities= relationship("ProjectActivity", back_populates="project", passive_deletes=True)

    # NEW: 프로젝트에 속한 세션들 (PracticeSession 관계)
    sessions  = relationship(
        "PracticeSession",
        back_populates="project",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="chk_projects_progress_0_100"),
        CheckConstraint("practice_hours >= 0", name="chk_projects_practice_hours_nonneg"),
        CheckConstraint("conversation_count >= 0", name="chk_projects_conversation_count_nonneg"),

        # 같은 class 안에서, 같은 사람이 같은 이름으로 두 번 만들지 못하게
        UniqueConstraint("owner_id", "class_id", "name", name="uq_projects_owner_class_name"),

        Index("idx_projects_owner_status", "owner_id", "status"),
        Index("idx_projects_owner_class", "owner_id", "class_id"),
        Index("idx_projects_last_activity", "last_activity_at"),
        {"schema": "user"},
    )


# ========== user.project_members ==========
class ProjectMember(Base):
    __tablename__ = "project_members"

    project_member_id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("user.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(Text, nullable=False, server_default=text("'member'"))
    status = Column(Text, nullable=False, server_default=text("'active'"))
    invited_at = Column(DateTime(timezone=True), nullable=True)
    joined_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("UserProject", back_populates="members", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
        Index("idx_project_members_project", "project_id"),
        Index("idx_project_members_user", "user_id"),
        {"schema": "user"},
    )


# ========== user.project_tags ==========
class ProjectTag(Base):
    __tablename__ = "project_tags"

    tag_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    color = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_project_tags_name", "name"),
        {"schema": "user"},
    )


# ========== user.project_tag_assignments ==========
class ProjectTagAssignment(Base):
    __tablename__ = "project_tag_assignments"

    assignment_id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("user.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id = Column(
        BigInteger,
        ForeignKey("user.project_tags.tag_id", ondelete="CASCADE"),
        nullable=False,
    )

    project = relationship("UserProject", back_populates="tags", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("project_id", "tag_id", name="uq_project_tag_assignments_project_tag"),
        Index("idx_project_tag_assignments_project", "project_id"),
        {"schema": "user"},
    )


# ========== user.project_metrics ==========
class ProjectMetric(Base):
    __tablename__ = "project_metrics"

    metric_id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("user.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_type = Column(Text, nullable=False)
    metric_value = Column(Numeric(18, 4), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("UserProject", back_populates="metrics", passive_deletes=True)

    __table_args__ = (
        Index("idx_project_metrics_project_time", "project_id", "recorded_at"),
        Index("idx_project_metrics_type_time", "metric_type", "recorded_at"),
        {"schema": "user"},
    )


# ========== user.project_activity ==========
class ProjectActivity(Base):
    __tablename__ = "project_activity"

    activity_id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("user.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    activity_type = Column(Text, nullable=False)
    details = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("UserProject", back_populates="activities", passive_deletes=True)

    __table_args__ = (
        Index("idx_project_activity_project_time", "project_id", "occurred_at"),
        Index("idx_project_activity_type_time", "activity_type", "occurred_at"),
        {"schema": "user"},
    )
