from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_serializer

from schemas.base import ORMModel

class PartnerProjectFinanceMonthlyUpsert(BaseModel):
    project_id: int = Field(..., ge=1)
    month: date
    contract_amount: Decimal = Field(default=Decimal('0'))
    api_cost: Decimal = Field(default=Decimal('0'))
    platform_fee: Decimal = Field(default=Decimal('0'))
    payout_amount: Decimal = Field(default=Decimal('0'))

    @field_serializer('contract_amount', 'api_cost', 'platform_fee', 'payout_amount', when_used='json')
    def _ser_money(self, v: Decimal) -> str:
        return format(v, 'f')

class PartnerProjectFinanceMonthlyOut(ORMModel):
    id: int
    project_id: int
    month: date
    contract_amount: Decimal
    api_cost: Decimal
    platform_fee: Decimal
    payout_amount: Decimal

    @field_serializer('contract_amount', 'api_cost', 'platform_fee', 'payout_amount', when_used='json')
    def _ser_money(self, v: Decimal) -> str:
        return format(v, 'f')
