# models/partner/course.py
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base
from models.partner.catalog import ModelCatalog  # 관계는 문자열로 참조하므로 필수는 아님


# ========== partner.courses ==========
class Course(Base):
    __tablename__ = "courses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 이 코스를 운영하는 org (교육기관)
    org_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )

    title = Column(Text, nullable=False)
    course_key = Column(Text, nullable=False)  # org 내에서 unique
    status = Column(
        Text,
        nullable=False,
        server_default=text("'draft'"),  # draft | active | archived
    )
    start_date = Column(Date)
    end_date = Column(Date)
    description = Column(Text)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # org ↔ course
    org = relationship(
        "Org",
        back_populates="courses",
        passive_deletes=True,
    )

    # course ↔ class
    classes = relationship(
        "Class",
        back_populates="course",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "course_key",
            name="uq_courses_org_course_key",
        ),
        CheckConstraint(
            "status IN ('draft','active','archived')",
            name="chk_courses_status",
        ),
        Index("idx_courses_org_status", "org_id", "status"),
        {"schema": "partner"},
    )


# ========== partner.classes ==========
class Class(Base):
    __tablename__ = "classes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    description = Column(Text)

    # 1 class : 1 partner(강사) = Partner.id
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 옵션: 특정 course에 속할 수도, 독립 class일 수도 있음
    course_id = Column(
        BigInteger,
        ForeignKey("partner.courses.id", ondelete="SET NULL"),
        nullable=True,
    )

    name = Column(Text, nullable=False)
    status = Column(
        Text,
        nullable=False,
        # planned | active | ended
        server_default=text("'planned'"),
    )
    start_at = Column(DateTime(timezone=True))
    end_at = Column(DateTime(timezone=True))
    capacity = Column(Integer)
    timezone = Column(Text, nullable=False, server_default=text("'UTC'"))
    location = Column(Text)
    online_url = Column(Text)
    invite_only = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # ==========================
    # LLM 관련 (강의실 단위)
    # ==========================
    primary_model_id = Column(
        BigInteger,
        ForeignKey("partner.model_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )

    allowed_model_ids = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # course ↔ class
    course = relationship(
        "Course",
        back_populates="classes",
        passive_deletes=True,
    )

    # 클래스 → 담당 파트너(강사, Partner)
    partner = relationship(
        "Partner",
        back_populates="classes",
        foreign_keys=[partner_id],
        passive_deletes=True,
    )

    # 클래스 → 기본 LLM 모델
    primary_model = relationship(
        "ModelCatalog",
        back_populates="primary_for_classes",
        foreign_keys=[primary_model_id],
        passive_deletes=True,
    )

    invite_codes = relationship(
        "InviteCode",
        back_populates="clazz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    enrollments = relationship(
        "Enrollment",
        back_populates="class_",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('planned','active','ended')",
            name="chk_classes_status",
        ),
        Index("idx_classes_course_status", "course_id", "status"),
        Index("idx_classes_partner_status", "partner_id", "status"),
        Index("idx_classes_primary_model", "primary_model_id"),
        {"schema": "partner"},
    )


# ========== partner.invite_codes ==========
class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 이 초대코드를 소유하는 파트너(강사, Partner)
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )

    # student 초대코드는 항상 특정 class 기준
    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="CASCADE"),
        nullable=False,
    )

    code = Column(Text, nullable=False)
    target_role = Column(
        Text,
        nullable=False,
        server_default=text("'student'"),
    )

    expires_at = Column(DateTime(timezone=True))
    max_uses = Column(Integer)  # NULL = unlimited
    used_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    status = Column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )

    # 실제 생성한 Partner (강사)
    created_by = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="SET NULL"),
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # class 관계
    clazz = relationship(
        "Class",
        back_populates="invite_codes",
        passive_deletes=True,
    )

    # 이 초대코드를 소유하는 강사(Partner)
    partner = relationship(
        "Partner",
        foreign_keys=[partner_id],
        back_populates="invite_codes",
        passive_deletes=True,
    )

    # 초대코드를 실제 생성한 Partner
    creator = relationship(
        "Partner",
        foreign_keys=[created_by],
        back_populates="created_invite_codes",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_invite_codes_code"),
        CheckConstraint(
            "used_count >= 0",
            name="chk_invite_codes_used_nonnegative",
        ),
        CheckConstraint(
            "(max_uses IS NULL) OR (used_count <= max_uses)",
            name="chk_invite_codes_used_le_max",
        ),
        CheckConstraint(
            "target_role = 'student'",
            name="chk_invite_codes_target_role_student_only",
        ),
        CheckConstraint(
            "status IN ('active','expired','disabled')",
            name="chk_invite_codes_status",
        ),
        Index("idx_invite_codes_partner_status", "partner_id", "status"),
        Index("idx_invite_codes_class_status", "class_id", "status"),
        {"schema": "partner"},
    )
