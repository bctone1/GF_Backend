from sqlalchemy import (
    Column, BigInteger, Integer, Text, Boolean,
    Date, DateTime, ForeignKey, UniqueConstraint,
    CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========== partner.courses ==========
class Course(Base):
    __tablename__ = "courses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(BigInteger, ForeignKey("partner.partners.id", ondelete="CASCADE"), nullable=False)

    title = Column(Text, nullable=False)
    code = Column(Text, nullable=False)  # unique within partner
    status = Column(Text, nullable=False, server_default=text("'draft'"))  # draft|active|archived
    start_date = Column(Date)
    end_date = Column(Date)
    description = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    classes = relationship("Class", back_populates="course", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "code", name="uq_courses_partner_code"),
        CheckConstraint("status IN ('draft','active','archived')", name="chk_courses_status"),
        Index("idx_courses_partner_status", "partner_id", "status"),
        {"schema": "partner"},
    )


# ========== partner.classes ==========
class Class(Base):
    __tablename__ = "classes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    course_id = Column(BigInteger, ForeignKey("partner.courses.id", ondelete="CASCADE"), nullable=False)

    name = Column(Text, nullable=False)
    section_code = Column(Text)  # optional per course
    status = Column(Text, nullable=False, server_default=text("'planned'"))  # planned|ongoing|ended
    start_at = Column(DateTime(timezone=True))
    end_at = Column(DateTime(timezone=True))
    capacity = Column(Integer)
    timezone = Column(Text, nullable=False, server_default=text("'UTC'"))
    location = Column(Text)
    online_url = Column(Text)
    invite_only = Column(Boolean, nullable=False, server_default=text("false"))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    course = relationship("Course", back_populates="classes", passive_deletes=True)
    instructors = relationship("ClassInstructor", back_populates="clazz", cascade="all, delete-orphan", passive_deletes=True)
    invite_codes = relationship("InviteCode", back_populates="clazz", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("course_id", "section_code", name="uq_classes_course_section", postgresql_nulls_not_distinct=True),
        CheckConstraint("status IN ('planned','ongoing','ended')", name="chk_classes_status"),
        Index("idx_classes_course_status", "course_id", "status"),
        {"schema": "partner"},
    )


# ========== partner.class_instructors ==========
class ClassInstructor(Base):
    __tablename__ = "class_instructors"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    class_id = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="CASCADE"), nullable=False)
    partner_user_id = Column(BigInteger, ForeignKey("partner.partner_users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False, server_default=text("'assistant'"))  # lead|assistant

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    clazz = relationship("Class", back_populates="instructors", passive_deletes=True)
    partner_user = relationship("PartnerUser", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("class_id", "partner_user_id", name="uq_class_instructors_unique"),
        CheckConstraint("role IN ('lead','assistant')", name="chk_class_instructors_role"),
        Index("idx_class_instructors_class", "class_id"),
        Index("idx_class_instructors_partner_user", "partner_user_id"),
        {"schema": "partner"},
    )


# ========== partner.invite_codes ==========
class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(BigInteger, ForeignKey("partner.partners.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="SET NULL"), nullable=True)

    code = Column(Text, nullable=False)  # globally unique
    target_role = Column(Text, nullable=False, server_default=text("'student'"))  # instructor|student
    expires_at = Column(DateTime(timezone=True))
    max_uses = Column(Integer)  # NULL = unlimited
    used_count = Column(Integer, nullable=False, server_default=text("0"))
    status = Column(Text, nullable=False, server_default=text("'active'"))  # active|expired|disabled
    created_by = Column(BigInteger, ForeignKey("partner.partner_users.id", ondelete="SET NULL"))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    clazz = relationship("Class", back_populates="invite_codes", passive_deletes=True)
    creator = relationship("PartnerUser", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("code", name="uq_invite_codes_code"),
        CheckConstraint("used_count >= 0", name="chk_invite_codes_used_nonnegative"),
        CheckConstraint("(max_uses IS NULL) OR (used_count <= max_uses)", name="chk_invite_codes_used_le_max"),
        CheckConstraint("target_role IN ('instructor','student')", name="chk_invite_codes_target_role"),
        CheckConstraint("status IN ('active','expired','disabled')", name="chk_invite_codes_status"),
        Index("idx_invite_codes_partner_status", "partner_id", "status"),
        {"schema": "partner"},
    )
