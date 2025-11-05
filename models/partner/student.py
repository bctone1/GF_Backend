# models/partner/student.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========== partner.students ==========
class Student(Base):
    __tablename__ = "students"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )

    full_name = Column(Text, nullable=False)
    email = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'active'"))
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    primary_contact = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    enrollments = relationship("Enrollment", back_populates="student", passive_deletes=True)

    __table_args__ = (
        Index("idx_students_partner_status", "partner_id", "status"),
        Index("idx_students_partner_email", "partner_id", "email"),
        {"schema": "partner"},
    )


# ========== partner.enrollments ==========
class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = Column(
        BigInteger,
        ForeignKey("partner.students.id", ondelete="CASCADE"),
        nullable=False,
    )

    status = Column(Text, nullable=False, server_default=text("'active'"))
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    progress_percent = Column(Numeric(5, 2), nullable=False, server_default=text("0"))

    project = relationship("Project", passive_deletes=True)
    student = relationship("Student", back_populates="enrollments", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("project_id", "student_id", name="uq_enrollments_project_student"),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="chk_enrollments_progress_0_100",
        ),
        Index("idx_enrollments_project", "project_id"),
        Index("idx_enrollments_student", "student_id"),
        Index("idx_enrollments_status_time", "status", "enrolled_at"),
        {"schema": "partner"},
    )
