# models/partner/partner_core.py

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

    # Org에 속한 파트너(강사/조교)들
    partners = relationship(
        "Partner",
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
class Partner(Base):
    """
    Org(기관)에 소속된 파트너(강사/어시스턴트).
    강사 번호(partner_id)는 이 테이블의 id.
    """
    __tablename__ = "partners"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # FK → Org.id
    org_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )

    # FK → AppUser.user_id (user.users.user_id)
    # 승격 시 이 user_id 기준으로 partner 레코드가 생성되고,
    # AppUser.partner_id 가 이 id 를 가리키게 됨.
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    full_name = Column(Text, nullable=False)
    email = Column(CITEXT, nullable=False)
    phone = Column(Text, nullable=True)

    # partner = 강사, assistant = 운영자(조교/매니저)
    role = Column(
        Text,
        nullable=False,
        server_default=text("'partner'"),
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 소속 Org
    org = relationship(
        "Org",
        back_populates="partners",
        passive_deletes=True,
    )

    # 담당 Class 들
    classes = relationship(
        "Class",
        back_populates="partner",
        foreign_keys="Class.partner_id",
        passive_deletes=True,
    )

    # 이 파트너 명의의 초대코드들 (InviteCode.partner_id)
    invite_codes = relationship(
        "InviteCode",
        back_populates="partner",
        foreign_keys="InviteCode.partner_id",
        passive_deletes=True,
    )

    # 이 파트너가 생성한 초대코드들 (InviteCode.created_by)
    created_invite_codes = relationship(
        "InviteCode",
        back_populates="creator",
        foreign_keys="InviteCode.created_by",
        passive_deletes=True,
    )

    __table_args__ = (
        # 한 유저당 하나의 파트너 레코드만 허용 (원하면 유지)
        UniqueConstraint("user_id", name="uq_partners_user_id"),
        # 같은 Org 안에서는 이메일도 유일
        UniqueConstraint("org_id", "email", name="uq_partners_org_email"),
        CheckConstraint("role IN ('partner','assistant')", name="chk_partners_role"),
        Index("idx_partners_email", "org_id", "email"),
        Index("idx_partners_active", "is_active"),
        Index("idx_partners_role", "role"),
        Index("idx_partners_last_login", "last_login_at"),
        {"schema": "partner"},
    )
