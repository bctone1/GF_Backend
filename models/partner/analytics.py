#### 파트너 이름 변경 시작 commit
# models/partner/analytics.py

from sqlalchemy import (
    Column, BigInteger, Text, Date, Numeric, ForeignKey,
    UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


# ========= partner.analytics_snapshots =========
class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.org.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date = Column(Date, nullable=False)  # 일 단위 스냅샷
    metric_type = Column(Text, nullable=False)
    metric_value = Column(Numeric(18, 4), nullable=False)
    meta = Column("metadata", JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "partner_id", "snapshot_date", "metric_type",
            name="uq_analytics_snapshots_partner_date_type",
        ),
        CheckConstraint("metric_value >= 0", name="chk_analytics_snapshots_value_nonneg"),
        Index("idx_analytics_snapshots_partner_date", "partner_id", "snapshot_date"),
        Index("idx_analytics_snapshots_type_date", "metric_type", "snapshot_date"),
        {"schema": "partner"},
    )


# ========= partner.enrollment_finance_monthly =========
class EnrollmentFinanceMonthly(Base):
    __tablename__ = "enrollment_finance_monthly"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    enrollment_id = Column(BigInteger, ForeignKey("partner.enrollments.id", ondelete="CASCADE"), nullable=False)
    month = Column(Date, nullable=False)  # YYYY-MM-01 고정

    contract_amount = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    api_cost        = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    platform_fee    = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    payout_amount   = Column(Numeric(14, 2), nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("enrollment_id", "month", name="uq_efm_enrollment_month"),
        CheckConstraint("contract_amount >= 0 AND api_cost >= 0 AND platform_fee >= 0 AND payout_amount >= 0",
                        name="chk_efm_amounts_nonneg"),
        # month는 해당 월의 첫날이어야 함 (PG 전용)
        CheckConstraint("date_trunc('month', month::timestamp) = month::timestamp",
                        name="chk_efm_month_is_first_day"),
        Index("idx_efm_enrollment_month", "enrollment_id", "month"),
        Index("idx_efm_partner_month", "partner_id", "month"),
        {"schema": "partner"},
    )
