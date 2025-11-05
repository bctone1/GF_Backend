# schemas/partner/billing.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import EmailStr
from schemas.base import ORMBase


# ========== partner.invoices ==========
class InvoiceCreate(ORMBase):
    partner_id: int
    invoice_number: str
    billing_period_start: date
    billing_period_end: date
    total_amount: Decimal
    status: Optional[str] = None  # default: 'draft'
    issued_at: Optional[datetime] = None
    due_date: Optional[date] = None


class InvoiceUpdate(ORMBase):
    invoice_number: Optional[str] = None
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    total_amount: Optional[Decimal] = None
    status: Optional[str] = None
    issued_at: Optional[datetime] = None
    due_date: Optional[date] = None


class InvoiceResponse(ORMBase):
    id: int
    partner_id: int
    invoice_number: str
    billing_period_start: date
    billing_period_end: date
    total_amount: Decimal
    status: str
    issued_at: Optional[datetime] = None
    due_date: Optional[date] = None


# ========== partner.invoice_items ==========
class InvoiceItemCreate(ORMBase):
    invoice_id: int
    project_id: Optional[int] = None
    description: str
    quantity: int = 1
    unit_price: Decimal = Decimal("0")
    amount: Decimal
    sort_order: Optional[int] = 0


class InvoiceItemUpdate(ORMBase):
    project_id: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    sort_order: Optional[int] = None


class InvoiceItemResponse(ORMBase):
    id: int
    invoice_id: int
    project_id: Optional[int] = None
    description: str
    quantity: int
    unit_price: Decimal
    amount: Decimal
    sort_order: int


# ========== partner.payouts ==========
class PayoutCreate(ORMBase):
    partner_id: int
    payout_number: str
    period_start: date
    period_end: date
    total_amount: Decimal
    status: Optional[str] = None  # default: 'pending'
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PayoutUpdate(ORMBase):
    payout_number: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_amount: Optional[Decimal] = None
    status: Optional[str] = None
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PayoutResponse(ORMBase):
    id: int
    partner_id: int
    payout_number: str
    period_start: date
    period_end: date
    total_amount: Decimal
    status: str
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ========== partner.payout_items ==========
class PayoutItemCreate(ORMBase):
    payout_id: int
    invoice_id: Optional[int] = None
    amount: Decimal
    fee_amount: Optional[Decimal] = Decimal("0")
    net_amount: Decimal
    notes: Optional[str] = None


class PayoutItemUpdate(ORMBase):
    invoice_id: Optional[int] = None
    amount: Optional[Decimal] = None
    fee_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    notes: Optional[str] = None


class PayoutItemResponse(ORMBase):
    id: int
    payout_id: int
    invoice_id: Optional[int] = None
    amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    notes: Optional[str] = None


# ========== partner.fee_rates ==========
class FeeRateCreate(ORMBase):
    partner_id: int
    fee_type: str
    percentage: Optional[Decimal] = None   # 0~100
    flat_amount: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None


class FeeRateUpdate(ORMBase):
    fee_type: Optional[str] = None
    percentage: Optional[Decimal] = None
    flat_amount: Optional[Decimal] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class FeeRateResponse(ORMBase):
    id: int
    partner_id: int
    fee_type: str
    percentage: Optional[Decimal] = None
    flat_amount: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None


# ========== partner.payout_accounts ==========
class PayoutAccountCreate(ORMBase):
    partner_id: int
    bank_name: str
    account_number_encrypted: str
    account_holder: str
    routing_number: Optional[str] = None
    currency: Optional[str] = None  # default: 'KRW'
    is_primary: Optional[bool] = None  # default: true


class PayoutAccountUpdate(ORMBase):
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


# ========== partner.business_profiles ==========
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
    tax_email: Optional[EmailStr] = None


class BusinessProfileUpdate(ORMBase):
    company_name: Optional[str] = None
    representative_name: Optional[str] = None
    address_line1: Optional[str] = None
    country: Optional[str] = None
    business_registration_number: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    tax_email: Optional[EmailStr] = None


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
    tax_email: Optional[EmailStr] = None
    created_at: datetime
