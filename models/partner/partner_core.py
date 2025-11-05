# models/partner/partner_core.py
from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========== partner.partners ==========
class Partner(Base):
    __tablename__ = "partners"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    code = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'active'"))
    timezone = Column(Text, nullable=False, server_default=text("'UTC'"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    users = relationship("PartnerUser", back_populates="partner", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("code", name="uq_partners_code"),
        Index("idx_partners_status", "status"),
        Index("idx_partners_created", "created_at"),
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
    # supervisor.users를 참조
    user_id = Column(
        BigInteger,
        ForeignKey("supervisor.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    full_name = Column(Text, nullable=False)
    email = Column(Text, nullable=False)
    phone = Column(Text, nullable=True)
    role = Column(Text, nullable=False, server_default=text("'partner_admin'"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    partner = relationship("Partner", back_populates="users", passive_deletes=True)

    __table_args__ = (
        # 원칙 반영: 파트너-유저 1회 매핑
        UniqueConstraint("partner_id", "user_id", name="uq_partner_users_partner_user"),
        # 이메일을 보조키로 조회할 때 사용
        Index("idx_partner_users_partner_email", "partner_id", "email"),
        Index("idx_partner_users_active", "is_active"),
        Index("idx_partner_users_role", "role"),
        {"schema": "partner"},
    )
