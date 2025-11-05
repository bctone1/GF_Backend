# models/partner/analytics.py
# READ-ONLY 집계. ETL/스케줄러만 적재.
from sqlalchemy import (
    Column, BigInteger, Text, Date, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


# ========= partner.analytics_snapshots =========
class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date = Column(Date, nullable=False)
    metric_type = Column(Text, nullable=False)
    metric_value = Column(Numeric(18, 4), nullable=False)
    metadata = Column(JSONB, nullable=True)

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


# ========= partner.project_finance_monthly =========
class ProjectFinanceMonthly(Base):
    __tablename__ = "project_finance_monthly"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    month = Column(Date, nullable=False)  # YYYY-MM-01 권장

    contract_amount = Column(Numeric(14, 2), nullable=False, default=0)
    api_cost = Column(Numeric(14, 2), nullable=False, default=0)
    platform_fee = Column(Numeric(14, 2), nullable=False, default=0)
    payout_amount = Column(Numeric(14, 2), nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("project_id", "month", name="uq_pfm_project_month"),
        CheckConstraint("contract_amount >= 0", name="chk_pfm_contract_nonneg"),
        CheckConstraint("api_cost >= 0", name="chk_pfm_api_cost_nonneg"),
        CheckConstraint("platform_fee >= 0", name="chk_pfm_platform_fee_nonneg"),
        CheckConstraint("payout_amount >= 0", name="chk_pfm_payout_nonneg"),
        Index("idx_pfm_project_month", "project_id", "month"),
        {"schema": "partner"},
    )
