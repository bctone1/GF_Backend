# models/backup.py
from sqlalchemy import (
    Column, BigInteger, String, Text, DateTime, Time, Numeric,
    ForeignKey, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


# ========== supervisor.backups ==========
class Backup(Base):
    __tablename__ = "backups"

    backup_id = Column(BigInteger, primary_key=True, autoincrement=True)

    frequency = Column(String(32), nullable=False)        # daily | weekly | monthly | cron | rrule 등
    time_utc = Column(Time(timezone=False), nullable=False)
    retention_period = Column(String(32), nullable=False) # e.g. '30d', '12w', '6m'
    storage_type = Column(String(32), nullable=False)     # s3 | gcs | azure | local 등
    config_json = Column(JSONB, nullable=True)

    status = Column(String(32), nullable=False, server_default=text("'active'"))  # active | paused | disabled
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('active','paused','disabled')", name="chk_backups_status"),
        Index("idx_backups_status_next", "status", "next_run_at"),
        Index("idx_backups_frequency", "frequency"),
        {"schema": "supervisor"},
    )


# ========== supervisor.backup_history ==========
class BackupHistory(Base):
    __tablename__ = "backup_history"

    history_id = Column(BigInteger, primary_key=True, autoincrement=True)

    backup_id = Column(
        BigInteger,
        ForeignKey("supervisor.backups.backup_id", ondelete="CASCADE"),
        nullable=False,
    )

    run_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    type = Column(String(32), nullable=True)              # full | incremental | differential 등
    size = Column(Numeric(18, 4), nullable=True)          # bytes 또는 선택 단위
    status = Column(String(32), nullable=False)           # queued | running | success | failed | partial
    location = Column(Text, nullable=True)                # 저장 경로/URL
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','success','failed','partial')",
            name="chk_backup_history_status",
        ),
        CheckConstraint("size IS NULL OR size >= 0", name="chk_backup_history_size_nonneg"),
        Index("idx_backup_history_backup_time", "backup_id", "run_at"),
        Index("idx_backup_history_status_time", "status", "run_at"),
        {"schema": "supervisor"},
    )
