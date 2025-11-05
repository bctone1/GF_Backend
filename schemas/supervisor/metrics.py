# schemas/supervisor/metrics.py
from __future__ import annotations
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from schemas.base import ORMBase


# ========== supervisor.metrics_snapshot ==========
class MetricsSnapshotResponse(ORMBase):
    snapshot_id: int
    metric_date: date
    metric_type: str
    organization_id: Optional[int] = None
    value: Decimal
    dimension_json: Optional[Dict[str, Any]] = None
    created_at: datetime


# ========== supervisor.cohort_metrics ==========
class CohortMetricResponse(ORMBase):
    cohort_id: int
    cohort_month: date
    metric_type: str
    month_offset: int
    value: Decimal
