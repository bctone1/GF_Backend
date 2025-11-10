# schemas/partner/analytics.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import ConfigDict

from schemas.base import ORMBase, Page  # Page[T] 제네릭 페이지 응답 사용


# ==============================
# READ-ONLY: partner.analytics_snapshots
# ==============================
class AnalyticsSnapshotResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

    id: int
    partner_id: int
    snapshot_date: date
    metric_type: str
    metric_value: Decimal
    meta: Optional[dict[str, Any]] = None  # "metadata"가 내장함수여서  ↔ 속성명 meta 매핑으로 바꿈

# 목록 응답 (목록 API 사용하기 좋음)
AnalyticsSnapshotPage = Page[AnalyticsSnapshotResponse]


# ==============================
# READ-ONLY: partner.enrollment_finance_monthly
# ==============================
class EnrollmentFinanceMonthlyResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

    id: int
    partner_id: int
    enrollment_id: int
    month: date  # YYYY-MM-01 관례
    contract_amount: Decimal
    api_cost: Decimal
    platform_fee: Decimal
    payout_amount: Decimal

# 목록 응답
EnrollmentFinanceMonthlyPage = Page[EnrollmentFinanceMonthlyResponse]
