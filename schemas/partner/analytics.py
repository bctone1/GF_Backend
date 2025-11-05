# schemas/partner/analytics.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Dict, Any
from schemas.base import ORMBase


# ========= partner.analytics_snapshots (READ-ONLY) =========
class AnalyticsSnapshotResponse(ORMBase):
    id: int
    partner_id: int
    snapshot_date: date
    metric_type: str
    metric_value: Decimal
    metadata: Optional[Dict[str, Any]] = None


# ========= partner.project_finance_monthly (READ-ONLY) =========
class ProjectFinanceMonthlyResponse(ORMBase):
    id: int
    project_id: int
    month: date
    contract_amount: Decimal
    api_cost: Decimal
    platform_fee: Decimal
    payout_amount: Decimal
