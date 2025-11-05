# schemas/supervisor/reports.py
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from schemas.base import ORMBase


# ========== supervisor.reports ==========
class ReportCreate(ORMBase):
    name: str
    type: str
    description: Optional[str] = None
    definition_json: Dict[str, Any]
    created_by: Optional[int] = None


class ReportUpdate(ORMBase):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    definition_json: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None


class ReportResponse(ORMBase):
    report_id: int
    name: str
    type: str
    description: Optional[str] = None
    definition_json: Dict[str, Any]
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ========== supervisor.scheduled_reports ==========
class ScheduledReportCreate(ORMBase):
    report_id: int
    frequency: str                 # 'cron:* * * * *' | 'rrule:FREQ=...'
    recipients: str                # comma-separated emails
    next_run_at: Optional[datetime] = None
    status: str = "active"         # active | paused | disabled
    created_by: Optional[int] = None


class ScheduledReportUpdate(ORMBase):
    report_id: Optional[int] = None
    frequency: Optional[str] = None
    recipients: Optional[str] = None
    next_run_at: Optional[datetime] = None
    status: Optional[str] = None
    created_by: Optional[int] = None


class ScheduledReportResponse(ORMBase):
    schedule_id: int
    report_id: int
    frequency: str
    recipients: str
    next_run_at: Optional[datetime] = None
    status: str
    last_run_at: Optional[datetime] = None
    created_by: Optional[int] = None


# ========== supervisor.report_runs ==========
class ReportRunCreate(ORMBase):
    report_id: int
    schedule_id: Optional[int] = None
    run_at: Optional[datetime] = None
    status: str = "queued"         # queued | running | success | failed
    generated_file_url: Optional[str] = None
    summary: Optional[str] = None


class ReportRunUpdate(ORMBase):
    run_at: Optional[datetime] = None
    status: Optional[str] = None
    generated_file_url: Optional[str] = None
    summary: Optional[str] = None


class ReportRunResponse(ORMBase):
    run_id: int
    report_id: int
    schedule_id: Optional[int] = None
    run_at: datetime
    status: str
    generated_file_url: Optional[str] = None
    summary: Optional[str] = None
