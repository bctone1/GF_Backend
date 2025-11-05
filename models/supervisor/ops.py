# models/ops.py
from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, DateTime, Numeric,
    CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


# ========== supervisor.system_metrics ==========
class SystemMetric(Base):
    __tablename__ = "system_metrics"

    metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    metric_type = Column(String(64), nullable=False)     # cpu_usage, mem_used_mb, qps 등
    resource = Column(String(128), nullable=False)       # 호스트명, 서비스명, 노드ID 등
    value = Column(Numeric(18, 4), nullable=False)
    unit = Column(String(32), nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    tags_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_system_metrics_type_time", "metric_type", "recorded_at"),
        Index("idx_system_metrics_resource_time", "resource", "recorded_at"),
        {"schema": "supervisor", "postgresql_partition_by": "RANGE (recorded_at)"},
    )


# ========== supervisor.service_status ==========
class ServiceStatus(Base):
    __tablename__ = "service_status"

    status_id = Column(BigInteger, primary_key=True, autoincrement=True)
    service_name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)      # ok, degraded, down, maintenance 등
    message = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_service_status_service_time", "service_name", "checked_at"),
        Index("idx_service_status_status_time", "status", "checked_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.alerts ==========
class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(BigInteger, primary_key=True, autoincrement=True)
    category = Column(String(64), nullable=False)         # billing, ops, security 등
    severity = Column(String(32), nullable=False)         # low, medium, high, critical
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, server_default=text("'open'"))  # open, acknowledged, resolved
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(BigInteger, nullable=True)       # FK 최소화 원칙: 하드 FK 없음

    __table_args__ = (
        CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="chk_alerts_severity",
        ),
        CheckConstraint(
            "status IN ('open','acknowledged','resolved')",
            name="chk_alerts_status",
        ),
        # 상태 전이 규칙 최소 보장: resolved면 resolved_at 필수, 미해결이면 NULL
        CheckConstraint(
            "(status = 'resolved' AND resolved_at IS NOT NULL) OR "
            "(status IN ('open','acknowledged') AND resolved_at IS NULL)",
            name="chk_alerts_resolved_fields",
        ),
        Index("idx_alerts_category_time", "category", "created_at"),
        Index("idx_alerts_severity_time", "severity", "created_at"),
        Index("idx_alerts_status_time", "status", "created_at"),
        # 미해결 전용 부분 인덱스
        Index(
            "idx_alerts_unresolved",
            "created_at",
            postgresql_where=text("status <> 'resolved'"),
        ),
        {"schema": "supervisor"},
    )


# ========== supervisor.events ==========
class Event(Base):
    __tablename__ = "events"

    event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(128), nullable=False)          # 도메인 소스: 'billing.invoice', 'user.signup' 등
    level = Column(String(32), nullable=False)            # info, warning, error
    message = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("level IN ('debug','info','warning','error','critical')", name="chk_events_level"),
        Index("idx_events_source_time", "source", "occurred_at"),
        Index("idx_events_level_time", "level", "occurred_at"),
        Index(
            "idx_events_errors_only",
            "occurred_at",
            postgresql_where=text("level IN ('error','critical')"),
        ),
        {"schema": "supervisor", "postgresql_partition_by": "RANGE (occurred_at)"},
    )


# ========== supervisor.logs ==========
class Log(Base):
    __tablename__ = "logs"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    service_name = Column(String(128), nullable=False)    # 앱/서비스 이름
    level = Column(String(32), nullable=False)            # debug, info, warning, error, critical
    message = Column(Text, nullable=False)
    context_json = Column(JSONB, nullable=True)
    logged_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("level IN ('debug','info','warning','error','critical')", name="chk_logs_level"),
        Index("idx_logs_service_time", "service_name", "logged_at"),
        Index("idx_logs_level_time", "level", "logged_at"),
        Index(
            "idx_logs_errors_only",
            "logged_at",
            postgresql_where=text("level IN ('error','critical')"),
        ),
        {"schema": "supervisor", "postgresql_partition_by": "RANGE (logged_at)"},
    )
