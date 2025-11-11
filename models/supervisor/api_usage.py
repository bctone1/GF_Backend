# models/api_usage.py
from sqlalchemy import (
    Column, BigInteger, String, Integer, DateTime, Numeric,
    ForeignKey, CheckConstraint, Index, text, PrimaryKeyConstraint
)
from sqlalchemy.sql import func
from models.base import Base


class ApiUsage(Base):
    __tablename__ = "api_usage"

    usage_id = Column(BigInteger, autoincrement=True, nullable=False)
    organization_id = Column(BigInteger, ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("supervisor.supervisors.user_id", ondelete="SET NULL"))
    provider = Column(String(64), nullable=False)
    endpoint = Column(String(128), nullable=False)
    tokens = Column(BigInteger, nullable=False, server_default=text("0"))
    cost = Column(Numeric(12, 4), nullable=False, server_default=text("0"))
    status = Column(String(32), nullable=False)
    response_time_ms = Column(Integer)
    requested_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('success','error','timeout','rate_limited')", name="chk_api_usage_status"),
        CheckConstraint("cost >= 0", name="chk_api_usage_cost_nonneg"),
        CheckConstraint("response_time_ms IS NULL OR response_time_ms >= 0", name="chk_api_usage_latency_nonneg"),
        CheckConstraint("tokens >= 0", name="chk_api_usage_tokens_nonneg"),
        PrimaryKeyConstraint("usage_id", "requested_at", name="pk_api_usage"),
        {
            "schema": "supervisor",
            "postgresql_partition_by": "RANGE (requested_at)",
        },
    )