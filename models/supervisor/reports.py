# models/reports.py
from sqlalchemy import (
    Column, BigInteger, String, Text, DateTime,
    ForeignKey, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from models.base import Base


# ========== supervisor.reports ==========
class Report(Base):
    __tablename__ = "reports"

    report_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    type = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    definition_json = Column(JSONB, nullable=False)

    created_by = Column(
        BigInteger,
        ForeignKey("supervisor.supervisors.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_reports_type", "type"),
        Index("idx_reports_name", "name"),
        {"schema": "supervisor"},
    )


# ========== supervisor.scheduled_reports ==========
class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    schedule_id = Column(BigInteger, primary_key=True, autoincrement=True)

    report_id = Column(
        BigInteger,
        ForeignKey("supervisor.reports.report_id", ondelete="CASCADE"),
        nullable=False,
    )

    frequency = Column(String(32), nullable=False)  # 예: 'cron:* * * * *' 또는 'rrule:FREQ=DAILY;...'
    recipients = Column(Text, nullable=False)       # 콤마 구분 이메일 등

    next_run_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, server_default=text("'active'"))  # active, paused, disabled
    last_run_at = Column(DateTime(timezone=True), nullable=True)

    created_by = Column(
        BigInteger,
        ForeignKey("supervisor.supervisors.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("status IN ('active','paused','disabled')", name="chk_scheduled_reports_status"),
        Index("idx_scheduled_reports_report", "report_id"),
        Index("idx_scheduled_reports_status_next", "status", "next_run_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.report_runs ==========
class ReportRun(Base):
    __tablename__ = "report_runs"

    run_id = Column(BigInteger, primary_key=True, autoincrement=True)

    report_id = Column(
        BigInteger,
        ForeignKey("supervisor.reports.report_id", ondelete="CASCADE"),
        nullable=False,
    )
    schedule_id = Column(
        BigInteger,
        ForeignKey("supervisor.scheduled_reports.schedule_id", ondelete="SET NULL"),
        nullable=True,
    )

    run_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(32), nullable=False)  # queued, running, success, failed
    generated_file_url = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('queued','running','success','failed')", name="chk_report_runs_status"),
        Index("idx_report_runs_report_time", "report_id", "run_at"),
        Index("idx_report_runs_status_time", "status", "run_at"),
        Index("idx_report_runs_schedule", "schedule_id"),
        {"schema": "supervisor"},
    )
