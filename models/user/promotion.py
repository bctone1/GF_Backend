# models/user/promotion.py
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, CITEXT
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from models.base import Base


# =========================
# user.partner_promotion_requests
# =========================
class PartnerPromotionRequest(Base):
    """
    유저가 '파트너/강사 승격'을 신청하는 요청 테이블 (user 스키마)

    - 생성 주체: user (일반 로그인 유저)
    - 처리 주체: supervisor (승인/거절, partner/partner_user 생성)
    """

    __tablename__ = "partner_promotion_requests"

    request_id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 요청한 user
    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    # 요청 시점 스냅샷
    email = Column(CITEXT, nullable=False)
    full_name = Column(Text, nullable=True)

    # 소속 기관명 (폼에서 입력한 기관/회사 이름)
    requested_org_name = Column(String(255), nullable=False)

    # 승인 시 부여할 파트너 역할 (예: partner_admin, instructor)
    target_role = Column(
        String(64),
        nullable=False,
        server_default=text("'partner_admin'"),
    )

    # 상태: pending / approved / rejected / cancelled
    status = Column(
        String(32),
        nullable=False,
        server_default=text("'pending'"),
    )

    # 타임스탬프
    requested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_reason = Column(Text, nullable=True)  # 승인/거절 사유

    # 승인 후 실제로 연결된 partner / partner_user
    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="SET NULL"),
        nullable=True,
    )
    partner_user_id = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 추가 정보 (전화번호, 교육 분야, 유입경로 등)
    meta = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # 선택: 필요하면 user 관계만 심플하게 잡아둠
    user = relationship("AppUser")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="chk_user_partner_promo_status",
        ),
        Index("ix_user_partner_promo_status", "status"),
        Index("ix_user_partner_promo_user", "user_id"),
        # 유저당 pending 1개만 허용
        Index(
            "ux_user_partner_promo_pending_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        {"schema": "user"},
    )
