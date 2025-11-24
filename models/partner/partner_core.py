from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import CITEXT
from models.base import Base


# ========== partner.org ==========
class Org(Base):
    __tablename__ = "org"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)           # 기관명
    code = Column(Text, nullable=False)           # 기관 코드
    status = Column(Text, nullable=False, server_default=text("'active'"))  # active|inactive|suspended
    timezone = Column(Text, nullable=False, server_default=text("'UTC'"))

    created_by = Column(
        BigInteger,
        ForeignKey("supervisor.supervisors.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Org에 속한 강사/조교들
    partner_users = relationship(
        "PartnerUser",
        back_populates="org",
        passive_deletes=True,
    )

    # Org에서 운영 중인 클래스들
    classes = relationship(
        "Class",
        back_populates="org",
        passive_deletes=True,
    )
    courses = relationship("Course", back_populates="org", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("code", name="uq_org_code"),
        CheckConstraint("status IN ('active','inactive','suspended')", name="chk_org_status"),
        Index("idx_org_status", "status"),
        Index("idx_org_created", "created_at"),
        Index("idx_org_created_by", "created_by"),
        {"schema": "partner"},
    )


# ========== partner.partner ==========
class PartnerUser(Base):
    """
    Org(기관)에 소속된 강사/어시스턴트.
    리팩토링 편의상 클래스 이름은 일단 PartnerUser 유지.
    """
    __tablename__ = "partner"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    org_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    full_name = Column(Text, nullable=False)
    email = Column(CITEXT, nullable=False)
    phone = Column(Text, nullable=True)

    # partner = 강사, assistant = 운영자/조직관리자
    role = Column(
        Text,
        nullable=False,
        server_default=text("'partner'"),  # partner | assistant
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 소속 Org
    org = relationship(
        "Org",
        back_populates="partner_users",
        passive_deletes=True,
    )
    classes = relationship("Class", back_populates="partner", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "user_id", name="uq_partner_user_user"),
        UniqueConstraint("partner_id", "email", name="uq_partner_user_email"),
        CheckConstraint("role IN ('partner','assistant')", name="chk_partner_role"),
        Index("idx_partner_email", "partner_id", "email"),
        Index("idx_partner_active", "is_active"),
        Index("idx_partner_role", "role"),
        Index("idx_partner_last_login", "last_login_at"),
        {"schema": "partner"},
    )
