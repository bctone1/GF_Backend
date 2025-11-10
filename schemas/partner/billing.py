# schemas/partner/billing.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import ConfigDict

from schemas.base import ORMBase, MoneyBase, Page
from schemas.enums import InvoiceStatus, PayoutStatus  # 'draft|issued|paid|overdue|void', 'pending|processing|paid|failed|canceled'


# ==============================
# invoices
# ==============================
class InvoiceCreate(ORMBase):
    partner_id: int
    invoice_number: str
    billing_period_start: date
    billing_period_end: date
    total_amount: Decimal
    status: Optional[InvoiceStatus] = None  # default 'draft' at DB
    issued_at: Optional[datetime] = None
    due_date: Optional[date] = None


class InvoiceUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    invoice_number: Optional[str] = None
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    total_amount: Optional[Decimal] = None
    status: Optional[InvoiceStatus] = None
    issued_at: Optional[datetime] = None
    due_date: Optional[date] = None


class InvoiceResponse(MoneyBase):
    id: int
    partner_id: int
    invoice_number: str
    billing_period_start: date
    billing_period_end: date
    total_amount: Decimal
    status: InvoiceStatus
    issued_at: Optional[datetime] = None
    due_date: Optional[date] = None
    # 선택: 함께 반환 시 사용
    items: Optional[List["InvoiceItemResponse"]] = None  # noqa: F821


InvoicePage = Page[InvoiceResponse]


# ==============================
# invoice_items
# ==============================
class InvoiceItemCreate(ORMBase):
    invoice_id: int
    description: str
    amount: Decimal  # DB에서 amount = quantity * unit_price 제약
    quantity: int = 1
    unit_price: Decimal = Decimal("0")
    sort_order: int = 0
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None


class InvoiceItemUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    quantity: Optional[int] = None
    unit_price: Optional[Decimal] = None
    sort_order: Optional[int] = None
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None


class InvoiceItemResponse(MoneyBase):
    id: int
    invoice_id: int
    description: str
    amount: Decimal
    quantity: int
    unit_price: Decimal
    sort_order: int
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None


InvoiceItemPage = Page[InvoiceItemResponse]


# ==============================
# payouts
# ==============================
class PayoutCreate(ORMBase):
    partner_id: int
    payout_number: str
    period_start: date
    period_end: date
    total_amount: Decimal
    status: Optional[PayoutStatus] = None  # default 'pending'
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PayoutUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    payout_number: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_amount: Optional[Decimal] = None
    status: Optional[PayoutStatus] = None
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PayoutResponse(MoneyBase):
    id: int
    partner_id: int
    payout_number: str
    period_start: date
    period_end: date
    total_amount: Decimal
    status: PayoutStatus
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    items: Optional[List["PayoutItemResponse"]] = None  # noqa: F821


PayoutPage = Page[PayoutResponse]


# ==============================
# payout_items
# ==============================
class PayoutItemCreate(ORMBase):
    payout_id: int
    amount: Decimal
    fee_amount: Decimal = Decimal("0")
    net_amount: Decimal  # DB 제약: net = amount - fee_amount
    invoice_id: Optional[int] = None
    notes: Optional[str] = None


class PayoutItemUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    amount: Optional[Decimal] = None
    fee_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    invoice_id: Optional[int] = None
    notes: Optional[str] = None


class PayoutItemResponse(MoneyBase):
    id: int
    payout_id: int
    amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    invoice_id: Optional[int] = None
    notes: Optional[str] = None


PayoutItemPage = Page[PayoutItemResponse]


# ==============================
# fee_rates
# ==============================
class FeeRateCreate(MoneyBase):
    partner_id: int
    fee_type: str  # 예: 'platform','processing'
    percentage: Optional[Decimal] = None  # 0~100
    flat_amount: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None


class FeeRateUpdate(MoneyBase):
    model_config = ConfigDict(from_attributes=False)
    fee_type: Optional[str] = None
    percentage: Optional[Decimal] = None
    flat_amount: Optional[Decimal] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class FeeRateResponse(MoneyBase):
    id: int
    partner_id: int
    fee_type: str
    percentage: Optional[Decimal] = None
    flat_amount: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None


FeeRatePage = Page[FeeRateResponse]


# ==============================
# payout_accounts
# ==============================
class PayoutAccountCreate(ORMBase):
    partner_id: int
    bank_name: str
    account_number_encrypted: str
    account_holder: str
    routing_number: Optional[str] = None
    currency: Optional[str] = None  # default 'KRW' at DB
    is_primary: Optional[bool] = None  # default true at DB


class PayoutAccountUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    bank_name: Optional[str] = None
    account_number_encrypted: Optional[str] = None
    account_holder: Optional[str] = None
    routing_number: Optional[str] = None
    currency: Optional[str] = None
    is_primary: Optional[bool] = None


class PayoutAccountResponse(ORMBase):
    id: int
    partner_id: int
    bank_name: str
    account_number_encrypted: str
    account_holder: str
    routing_number: Optional[str] = None
    currency: str
    is_primary: bool
    created_at: datetime


PayoutAccountPage = Page[PayoutAccountResponse]


# ==============================
# business_profiles
# ==============================
class BusinessProfileCreate(ORMBase):
    partner_id: int
    company_name: str
    representative_name: str
    address_line1: str
    country: str
    business_registration_number: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    tax_email: Optional[str] = None


class BusinessProfileUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    company_name: Optional[str] = None
    representative_name: Optional[str] = None
    address_line1: Optional[str] = None
    country: Optional[str] = None
    business_registration_number: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    tax_email: Optional[str] = None


class BusinessProfileResponse(ORMBase):
    partner_id: int
    business_registration_number: Optional[str] = None
    company_name: str
    representative_name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str
    tax_email: Optional[str] = None
    created_at: datetime

# ==============================
# class_finance_monthly
# ==============================
class ClassFinanceMonthlyCreate(MoneyBase):
    class_id: int
    month: date  # YYYY-MM-01
    contract_amount: Decimal = Decimal("0")
    api_cost: Decimal = Decimal("0")
    platform_fee: Decimal = Decimal("0")
    payout_amount: Decimal = Decimal("0")


class ClassFinanceMonthlyUpdate(MoneyBase):
    model_config = ConfigDict(from_attributes=False)
    contract_amount: Optional[Decimal] = None
    api_cost: Optional[Decimal] = None
    platform_fee: Optional[Decimal] = None
    payout_amount: Optional[Decimal] = None


class ClassFinanceMonthlyResponse(MoneyBase):
    id: int
    class_id: int
    month: date
    contract_amount: Decimal
    api_cost: Decimal
    platform_fee: Decimal
    payout_amount: Decimal


ClassFinanceMonthlyPage = Page[ClassFinanceMonthlyResponse]
