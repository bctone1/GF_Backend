# models/partner/student.py
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

    # Partner(강사) 기준 학생
    # DB에는 partner.students.partner_id -> partner.partners(id) FK 있음
    # ORM 쪽에서는 단순 정수 컬럼로만 둔다 (NoReferencedTableError 회피용)
    partner_id = Column(
        BigInteger,
        nullable=False,
    )

    # 이 Student가 매핑되는 AppUser (일반 유저) - 선택적
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="SET NULL"),
        nullable=True,
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

        # 상태 필터용
        Index("idx_students_partner_status", "partner_id", "status"),

        # partner 내 이메일 단일, NULL 허용
        Index("idx_students_partner_email", "partner_id", "email"),
        Index(
            "uq_students_partner_email_notnull",
            "partner_id", "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),

        # AppUser 매핑 검색용
        Index("idx_students_user_id", "user_id"),

        # 같은 파트너에서 같은 user_id로 중복 Student 생성 방지 (user_id NOT NULL인 경우만)
        Index(
            "uq_students_partner_user_notnull",
            "partner_id", "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),

        {"schema": "partner"},
    )

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

    invite_code_id = Column(
        BigInteger,
        ForeignKey("partner.invite_codes.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(Text, nullable=False, server_default=text("'active'"))
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    class_ = relationship("Class", back_populates="enrollments", passive_deletes=True)
    student = relationship("Student", back_populates="enrollments", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_enrollments_class_student"),
        CheckConstraint("status IN ('active','inactive','completed','dropped')", name="chk_enrollments_status"),
        CheckConstraint("(completed_at IS NULL) OR (completed_at >= enrolled_at)", name="chk_enrollments_time"),
        Index("idx_enrollments_class", "class_id"),
        Index("idx_enrollments_student", "student_id"),
        Index("idx_enrollments_status_time", "status", "enrolled_at"),
        {"schema": "partner"},
    )
