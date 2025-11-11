# models/partner/partner_core.py
from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import CITEXT
from models.base import Base


# ========== partner.partners ==========
class Partner(Base):
    __tablename__ = "partners"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    code = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'active'"))  # active|inactive|suspended
    timezone = Column(Text, nullable=False, server_default=text("'UTC'"))

    # 추가: 생성자(슈퍼바이저 사용자)
    created_by = Column(
        BigInteger,
        ForeignKey("supervisor.supervisors.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    users = relationship("PartnerUser", back_populates="partner", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("code", name="uq_partners_code"),
        CheckConstraint("status IN ('active','inactive','suspended')", name="chk_partners_status"),
        Index("idx_partners_status", "status"),
        Index("idx_partners_created", "created_at"),
        Index("idx_partners_created_by", "created_by"),
        {"schema": "partner"},
    )


# ========== partner.partner_users ==========
class PartnerUser(Base):
    __tablename__ = "partner_users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    # user.users.user_id 참조
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    full_name = Column(Text, nullable=False)
    email = Column(CITEXT, nullable=False)  # 대소문자 무시
    phone = Column(Text, nullable=True)
    role = Column(Text, nullable=False, server_default=text("'partner_admin'"))  # partner_admin|instructor|assistant
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    partner = relationship("Partner", back_populates="users", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "user_id", name="uq_partner_users_partner_user"),
        UniqueConstraint("partner_id", "email", name="uq_partner_users_partner_email"),
        CheckConstraint("role IN ('partner_admin','instructor','assistant')", name="chk_partner_users_role"),
        Index("idx_partner_users_partner_email", "partner_id", "email"),
        Index("idx_partner_users_active", "is_active"),
        Index("idx_partner_users_role", "role"),
        Index("idx_partner_users_last_login", "last_login_at"),
        {"schema": "partner"},
    )
