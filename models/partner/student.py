from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import CITEXT
from models.base import Base


# ========== partner.students ==========
class Student(Base):
    __tablename__ = "students"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )

    full_name = Column(Text, nullable=False)
    email = Column(CITEXT, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'active'"))  # active|inactive|archived
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    primary_contact = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    enrollments = relationship("Enrollment", back_populates="student", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("status IN ('active','inactive','archived')", name="chk_students_status"),
        Index("idx_students_partner_status", "partner_id", "status"),
        Index("idx_students_partner_email", "partner_id", "email"),
        # 파트너 내 이메일 단일, NULL 허용
        Index(
            "uq_students_partner_email_notnull",
            "partner_id", "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        {"schema": "partner"},
    )


# ========== partner.enrollments ==========
class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = Column(
        BigInteger,
        ForeignKey("partner.students.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 선택: 초대코드 트래킹
    invite_code_id = Column(
        BigInteger,
        ForeignKey("partner.invite_codes.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(Text, nullable=False, server_default=text("'active'"))  # active|inactive|completed|dropped
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    progress_percent = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    final_grade = Column(Text, nullable=True)

    # 표준 이름: class_  (Class 모델의 enrollments와 짝)
    class_ = relationship("Class", back_populates="enrollments", passive_deletes=True)
    student = relationship("Student", back_populates="enrollments", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_enrollments_class_student"),
        CheckConstraint("status IN ('active','inactive','completed','dropped')", name="chk_enrollments_status"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="chk_enrollments_progress_0_100"),
        CheckConstraint("(completed_at IS NULL) OR (completed_at >= enrolled_at)", name="chk_enrollments_time"),
        Index("idx_enrollments_class", "class_id"),
        Index("idx_enrollments_student", "student_id"),
        Index("idx_enrollments_status_time", "status", "enrolled_at"),
        {"schema": "partner"},
    )
