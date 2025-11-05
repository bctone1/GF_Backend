# schemas/supervisor/billing.py
from __future__ import annotations
from typing import Optional
from decimal import Decimal
from datetime import datetime, date
from schemas.base import MoneyBase


# ========== supervisor.transactions ==========
class TransactionCreate(MoneyBase):
    organization_id: int
    plan_id: Optional[int] = None
    amount: Decimal
    currency: str = "USD"
    status: str                  # pending | succeeded | failed | refunded
    payment_method: Optional[str] = None
    transaction_type: str = "subscription"  # subscription | usage | adjustment
    transacted_at: Optional[datetime] = None
    invoice_url: Optional[str] = None


class TransactionUpdate(MoneyBase):
    organization_id: Optional[int] = None
    plan_id: Optional[int] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    transaction_type: Optional[str] = None
    transacted_at: Optional[datetime] = None
    invoice_url: Optional[str] = None


class TransactionResponse(MoneyBase):
    transaction_id: int
    organization_id: int
    plan_id: Optional[int] = None
    amount: Decimal
    currency: str
    status: str
    payment_method: Optional[str] = None
    transaction_type: str
    transacted_at: datetime
    invoice_url: Optional[str] = None


# ========== supervisor.invoices ==========
class InvoiceCreate(MoneyBase):
    organization_id: int
    billing_period_start: date
    billing_period_end: date
    total_amount: Decimal
    status: str                  # draft | issued | paid | overdue | void
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


class InvoiceUpdate(MoneyBase):
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    total_amount: Optional[Decimal] = None
    status: Optional[str] = None
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


class InvoiceResponse(MoneyBase):
    invoice_id: int
    organization_id: int
    billing_period_start: date
    billing_period_end: date
    total_amount: Decimal
    status: str
    issued_at: datetime
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


# ========== supervisor.subscription_changes ==========
class SubscriptionChangeCreate(MoneyBase):
    organization_id: int
    old_plan_id: Optional[int] = None
    new_plan_id: Optional[int] = None
    effective_at: datetime
    reason: Optional[str] = None
    changed_by: Optional[int] = None


class SubscriptionChangeUpdate(MoneyBase):
    old_plan_id: Optional[int] = None
    new_plan_id: Optional[int] = None
    effective_at: Optional[datetime] = None
    reason: Optional[str] = None
    changed_by: Optional[int] = None


class SubscriptionChangeResponse(MoneyBase):
    change_id: int
    organization_id: int
    old_plan_id: Optional[int] = None
    new_plan_id: Optional[int] = None
    effective_at: datetime
    reason: Optional[str] = None
    changed_by: Optional[int] = None


# ========== supervisor.arpu_history (READ-ONLY) ==========
class ArpuHistoryResponse(MoneyBase):
    record_id: int
    period: date
    arpu_value: Decimal
    plan_id: Optional[int] = None
