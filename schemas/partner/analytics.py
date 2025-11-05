from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, Field, field_serializer

from schemas.base import ORMModel

class PartnerAnalyticsSnapshotCreate(BaseModel):
    partner_id: int = Field(..., ge=1)
    snapshot_date: date
    metric_type: str
    metric_value: Decimal
    metadata: Optional[dict[str, Any]] = None

    @field_serializer('metric_value', when_used='json')
    def _ser_metric(self, v: Decimal) -> str:
        return format(v, 'f')

class PartnerAnalyticsSnapshotOut(ORMModel):
    id: int
    partner_id: int
    snapshot_date: date
    metric_type: str
    metric_value: Decimal
    metadata: Optional[dict[str, Any]] = None

    @field_serializer('metric_value', when_used='json')
    def _ser_metric(self, v: Decimal) -> str:
        return format(v, 'f')
