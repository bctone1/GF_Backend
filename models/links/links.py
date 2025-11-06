# models/links/links.py
from sqlalchemy import (
    Column, BigInteger, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from models.base import Base

# ====================== links.partner_org_link ======================
class PartnerOrgLink(Base):
    __tablename__ = "partner_org_link"

    link_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )

    status = Column(Text, nullable=False, server_default=text("'active'"))
    is_primary = Column(Boolean, nullable=False, server_default=text("false"))
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "partner_id", name="uq_partner_org"),
        # 조직당 primary 링크 하나만 허용(부분 유니크)
        Index(
            "uq_partner_org_primary_once",
            "organization_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
        Index("idx_partner_org_org", "organization_id"),
        Index("idx_partner_org_partner", "partner_id"),
        CheckConstraint(
            "status IN ('active','inactive','suspended','draft')",
            name="chk_partner_org_link_status",
        ),
        {"schema": "links"},  # dict는 반드시 마지막
    )


# ======================== links.org_user_link ========================
class OrgUserLink(Base):
    __tablename__ = "org_user_link"

    link_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey('user.users.user_id', ondelete="CASCADE"),
        nullable=False,
    )

    role = Column(Text, nullable=False, server_default=text("'member'"))
    status = Column(Text, nullable=False, server_default=text("'active'"))
    notes = Column(Text, nullable=True)

    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    left_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
        Index("idx_org_user_org", "organization_id"),
        Index("idx_org_user_user", "user_id"),
        Index("idx_org_user_role", "role"),
        Index("idx_org_user_status", "status"),
        Index(  # 활성 멤버 조회 최적화
            "idx_org_user_active",
            "organization_id",
            "user_id",
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint(
            "status IN ('active','inactive','suspended','draft')",
            name="chk_org_user_link_status",
        ),
        CheckConstraint(
            "role IN ('owner','admin','manager','member','student','instructor')",
            name="chk_org_user_link_role",
        ),
        CheckConstraint(
            "(left_at IS NULL) OR (left_at >= joined_at)",
            name="chk_org_user_link_left_after_join",
        ),
        {"schema": "links"},  # dict는 반드시 마지막
    )

