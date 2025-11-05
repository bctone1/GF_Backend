# models/metrics.py
from sqlalchemy import (
    Column, BigInteger, String, Integer, DateTime, Date, Numeric,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base


# ========== supervisor.metrics_snapshot ==========
class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshot"

    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    metric_date = Column(Date, nullable=False)
    metric_type = Column(String(64), nullable=False)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=True,  # 전역 스냅샷 허용 시 NULL
    )

    value = Column(Numeric(18, 4), nullable=False)
    dimension_json = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # 조회 패턴 최적화 인덱스
        Index("idx_metrics_snapshot_date", "metric_date"),
        Index("idx_metrics_snapshot_type_date", "metric_type", "metric_date"),
        Index("idx_metrics_snapshot_org_date", "organization_id", "metric_date"),
        # 필요 시 중복 방지(옵션): 같은 날짜·타입·조직 1건
        # UniqueConstraint("metric_date", "metric_type", "organization_id", name="uq_metrics_snapshot_key"),
        {"schema": "supervisor"},
    )


# ========== supervisor.cohort_metrics ==========
class CohortMetric(Base):
    __tablename__ = "cohort_metrics"

    cohort_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cohort_month = Column(Date, nullable=False)         # 코호트 유입 월(YYYY-MM-01 관례)
    metric_type = Column(String(64), nullable=False)    # 예: retention_rate, mrr, wau 등
    month_offset = Column(Integer, nullable=False)      # 코호트 기준 경과 개월(0,1,2,...)
    value = Column(Numeric(18, 4), nullable=False)

    __table_args__ = (
        # 중복 방지 키
        UniqueConstraint("cohort_month", "metric_type", "month_offset", name="uq_cohort_metrics_key"),
        # 조회 인덱스
        Index("idx_cohort_metrics_month", "cohort_month"),
        Index("idx_cohort_metrics_type_offset", "metric_type", "month_offset"),
        {"schema": "supervisor"},
    )
