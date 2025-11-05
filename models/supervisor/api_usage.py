# models/api_usage.py
from sqlalchemy import (
    Column, BigInteger, String, Integer, DateTime, Numeric,
    ForeignKey, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from models.base import Base


class ApiUsage(Base):
    __tablename__ = "api_usage"

    usage_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("supervisor.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    provider = Column(String(64), nullable=False)
    endpoint = Column(String(128), nullable=False)

    tokens = Column(BigInteger, nullable=False, server_default=text("0"))
    cost = Column(Numeric(12, 4), nullable=False, server_default=text("0"))

    status = Column(String(32), nullable=False)          # 'success' | 'error' | 'timeout' | 'rate_limited'
    response_time_ms = Column(Integer, nullable=True)

    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # 값 제약
        CheckConstraint("tokens >= 0", name="chk_api_usage_tokens_nonneg"),
        CheckConstraint("cost >= 0", name="chk_api_usage_cost_nonneg"),
        CheckConstraint("response_time_ms IS NULL OR response_time_ms >= 0", name="chk_api_usage_latency_nonneg"),
        CheckConstraint("status IN ('success','error','timeout','rate_limited')", name="chk_api_usage_status"),
        # 조회 인덱스
        Index("idx_api_usage_org_time", "organization_id", "requested_at"),
        Index("idx_api_usage_provider_time", "provider", "requested_at"),
        Index("idx_api_usage_endpoint_time", "endpoint", "requested_at"),
        Index("idx_api_usage_status_time", "status", "requested_at"),
        # 오류·타임아웃 전용 부분 인덱스
        Index("idx_api_usage_errors_only", "requested_at", postgresql_where=text("status <> 'success'")),
        # 스키마 및 파티셔닝(월별 RANGE, 실제 파티션 생성은 마이그레이션에서 처리)
        {"schema": "supervisor", "postgresql_partition_by": "RANGE (requested_at)"},
    )
