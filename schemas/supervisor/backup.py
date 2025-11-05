# schemas/supervisor/backup.py
from __future__ import annotations
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, time
from schemas.base import ORMBase


# ========== supervisor.backups ==========
class BackupCreate(ORMBase):
    frequency: str                    # daily | weekly | monthly | cron | rrule
    time_utc: time
    retention_period: str             # '30d' | '12w' | '6m' 등
    storage_type: str                 # s3 | gcs | azure | local
    config_json: Optional[Dict[str, Any]] = None
    status: str = "active"            # active | paused | disabled
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None


class BackupUpdate(ORMBase):
    frequency: Optional[str] = None
    time_utc: Optional[time] = None
    retention_period: Optional[str] = None
    storage_type: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None


class BackupResponse(ORMBase):
    backup_id: int
    frequency: str
    time_utc: time
    retention_period: str
    storage_type: str
    config_json: Optional[Dict[str, Any]] = None
    status: str
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None


# ========== supervisor.backup_history ==========
class BackupHistoryCreate(ORMBase):
    backup_id: int
    run_at: Optional[datetime] = None
    type: Optional[str] = None              # full | incremental | differential
    size: Optional[Decimal] = None
    status: str                              # queued | running | success | failed | partial
    location: Optional[str] = None
    notes: Optional[str] = None


class BackupHistoryUpdate(ORMBase):
    run_at: Optional[datetime] = None
    type: Optional[str] = None
    size: Optional[Decimal] = None
    status: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class BackupHistoryResponse(ORMBase):
    history_id: int
    backup_id: int
    run_at: datetime
    type: Optional[str] = None
    size: Optional[Decimal] = None
    status: str
    location: Optional[str] = None
    notes: Optional[str] = None
