# models/partner/billing.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, Date, DateTime, Numeric, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base

# ========== partner.invoices ==========
class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    invoice_number = Column(Text, nullable=False)

    billing_period_start = Column(Date, nullable=False)
    billing_period_end   = Column(Date, nullable=False)

    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(Text, nullable=False, server_default=text("'draft'"))  # draft|issued|paid|overdue|void
    issued_at = Column(DateTime(timezone=True))
    due_date  = Column(Date)

    items = relationship("InvoiceItem", back_populates="invoice", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "invoice_number", name="uq_invoices_partner_number"),
        CheckConstraint("total_amount >= 0", name="chk_invoices_total_nonneg"),
        CheckConstraint("billing_period_end >= billing_period_start", name="chk_invoices_period_valid"),
        CheckConstraint("status IN ('draft','issued','paid','overdue','void')", name="chk_invoices_status"),
        # 마감일은 청구기간 종료일 이상(또는 NULL)
        CheckConstraint("(due_date IS NULL) OR (due_date >= billing_period_end)", name="chk_invoices_due_after_period"),
        Index("idx_invoices_partner_period", "partner_id", "billing_period_start"),
        Index("idx_invoices_status", "status"),
        {"schema": "partner"},
    )

# ========== partner.invoice_items ==========
class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    invoice_id = Column(BigInteger, ForeignKey("partner.invoices.id", ondelete="CASCADE"), nullable=False)

    # 프로젝트 참조 제거 → 학생/수강 기반
    enrollment_id = Column(BigInteger, ForeignKey("partner.enrollments.id", ondelete="SET NULL"))
    student_id    = Column(BigInteger, ForeignKey("partner.students.id", ondelete="SET NULL"))

    description = Column(Text, nullable=False)
    quantity    = Column(Integer, nullable=False, server_default=text("1"))
    unit_price  = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    amount      = Column(Numeric(14, 2), nullable=False)
    sort_order  = Column(Integer, nullable=False, server_default=text("0"))

    invoice = relationship("Invoice", back_populates="items", passive_deletes=True)
    # enrollment = relationship("Enrollment", passive_deletes=True)
    # student = relationship("Student", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="chk_invoice_items_qty_pos"),
        CheckConstraint("unit_price >= 0", name="chk_invoice_items_unit_price_nonneg"),
        CheckConstraint("amount >= 0", name="chk_invoice_items_amount_nonneg"),
        CheckConstraint("sort_order >= 0", name="chk_invoice_items_sort_nonneg"),
        # 최소 한 개 식별자 확보: 수강 또는 학생
        CheckConstraint("(enrollment_id IS NOT NULL) OR (student_id IS NOT NULL)", name="chk_invoice_items_target_present"),
        # 금액 일치(정밀도 Numeric이므로 허용)
        CheckConstraint("amount = quantity * unit_price", name="chk_invoice_items_amount_eq"),
        Index("idx_invoice_items_invoice_sort", "invoice_id", "sort_order"),
        Index("idx_invoice_items_enrollment", "enrollment_id"),
        Index("idx_invoice_items_student", "student_id"),
        {"schema": "partner"},
    )

# ========== partner.payouts ==========
class Payout(Base):
    __tablename__ = "payouts"
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    payout_number = Column(Text, nullable=False)

    period_start = Column(Date, nullable=False)
    period_end   = Column(Date, nullable=False)

    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(Text, nullable=False, server_default=text("'pending'"))  # pending|processing|paid|failed|canceled
    initiated_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    items = relationship("PayoutItem", back_populates="payout", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "payout_number", name="uq_payouts_partner_number"),
        CheckConstraint("total_amount >= 0", name="chk_payouts_total_nonneg"),
        CheckConstraint("period_end >= period_start", name="chk_payouts_period_valid"),
        CheckConstraint("status IN ('pending','processing','paid','failed','canceled')", name="chk_payouts_status"),
        Index("idx_payouts_partner_period", "partner_id", "period_start"),
        Index("idx_payouts_status", "status"),
        {"schema": "partner"},
    )

# ========== partner.payout_items ==========
class PayoutItem(Base):
    __tablename__ = "payout_items"
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    payout_id = Column(BigInteger, ForeignKey("partner.payouts.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(BigInteger, ForeignKey("partner.invoices.id", ondelete="SET NULL"))

    amount     = Column(Numeric(14, 2), nullable=False)
    fee_amount = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    net_amount = Column(Numeric(14, 2), nullable=False)
    notes = Column(Text)

    payout = relationship("Payout", back_populates="items", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("amount >= 0", name="chk_payout_items_amount_nonneg"),
        CheckConstraint("fee_amount >= 0", name="chk_payout_items_fee_nonneg"),
        CheckConstraint("net_amount >= 0", name="chk_payout_items_net_nonneg"),
        # 정합: net = amount - fee
        CheckConstraint("net_amount = amount - fee_amount", name="chk_payout_items_net_eq"),
        Index("idx_payout_items_payout", "payout_id"),
        Index("idx_payout_items_invoice", "invoice_id"),
        {"schema": "partner"},
    )

# ========== partner.fee_rates ==========
class FeeRate(Base):
    __tablename__ = "fee_rates"
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)
    fee_type   = Column(Text, nullable=False)  # 'platform', 'processing', ...

    percentage  = Column(Numeric(5, 2))
    flat_amount = Column(Numeric(14, 2))

    effective_from = Column(Date, nullable=False)
    effective_to   = Column(Date)

    __table_args__ = (
        UniqueConstraint("partner_id", "fee_type", "effective_from", name="uq_fee_rates_key"),
        CheckConstraint("percentage IS NULL OR (percentage >= 0 AND percentage <= 100)", name="chk_fee_rates_pct_range"),
        CheckConstraint("flat_amount IS NULL OR flat_amount >= 0", name="chk_fee_rates_flat_nonneg"),
        CheckConstraint("(percentage IS NOT NULL) OR (flat_amount IS NOT NULL)", name="chk_fee_rates_one_of_pct_flat"),
        CheckConstraint("(effective_to IS NULL) OR (effective_to >= effective_from)", name="chk_fee_rates_period_valid"),
        Index("idx_fee_rates_partner_type", "partner_id", "fee_type"),
        {"schema": "partner"},
    )
    # 참고: 기간 겹침 방지는 PG EXCLUDE( daterange )로 구현 가능(선택)

# ========== partner.payout_accounts ==========
class PayoutAccount(Base):
    __tablename__ = "payout_accounts"
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), nullable=False)

    bank_name = Column(Text, nullable=False)
    account_number_encrypted = Column(Text, nullable=False)
    account_holder = Column(Text, nullable=False)
    routing_number = Column(Text)
    currency = Column(Text, nullable=False, server_default=text("'KRW'"))
    is_primary = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # 파셜 유니크: 파트너당 primary 하나
        Index("uq_payout_accounts_partner_primary", "partner_id", unique=True, postgresql_where=text("is_primary = true")),
        Index("idx_payout_accounts_partner", "partner_id"),
        CheckConstraint("currency IN ('KRW','USD','JPY','EUR')", name="chk_payout_accounts_currency"),  # 필요 통화만
        {"schema": "partner"},
    )

# ========== partner.business_profiles ==========
class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    partner_id = Column(BigInteger, ForeignKey("partner.org.id", ondelete="CASCADE"), primary_key=True, nullable=False)

    business_registration_number = Column(Text)
    company_name        = Column(Text, nullable=False)
    representative_name = Column(Text, nullable=False)
    address_line1 = Column(Text, nullable=False)
    address_line2 = Column(Text)
    city   = Column(Text)
    state  = Column(Text)
    postal_code = Column(Text)
    country = Column(Text, nullable=False)
    tax_email = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_business_profiles_country", "country"),
        {"schema": "partner"},
    )

# ========== partner.class_finance_monthly ==========
class ClassFinanceMonthly(Base):
    __tablename__ = "class_finance_monthly"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    class_id = Column(BigInteger, ForeignKey("partner.classes.id", ondelete="CASCADE"), nullable=False)
    month = Column(Date, nullable=False)  # YYYY-MM-01

    contract_amount = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    api_cost        = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    platform_fee    = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    payout_amount   = Column(Numeric(14, 2), nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("class_id", "month", name="uq_class_finance_month"),
        CheckConstraint("contract_amount >= 0 AND api_cost >= 0 AND platform_fee >= 0 AND payout_amount >= 0",
                        name="chk_cfm_amounts_nonneg"),
        CheckConstraint("date_trunc('month', month::timestamp) = month::timestamp",
                        name="chk_cfm_month_is_first_day"),
        Index("idx_class_finance_class_month", "class_id", "month"),
        {"schema": "partner"},
    )
