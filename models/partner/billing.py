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

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_number = Column(Text, nullable=False)

    billing_period_start = Column(Date, nullable=False)
    billing_period_end = Column(Date, nullable=False)

    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(Text, nullable=False, server_default=text("'draft'"))  # draft/issued/paid/overdue/void
    issued_at = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(Date, nullable=True)

    items = relationship("InvoiceItem", back_populates="invoice", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "invoice_number", name="uq_invoices_partner_number"),
        CheckConstraint("total_amount >= 0", name="chk_invoices_total_nonneg"),
        CheckConstraint("billing_period_end >= billing_period_start", name="chk_invoices_period_valid"),
        Index("idx_invoices_partner_period", "partner_id", "billing_period_start"),
        Index("idx_invoices_status", "status"),
        {"schema": "partner"},
    )


# ========== partner.invoice_items ==========
class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    invoice_id = Column(
        BigInteger,
        ForeignKey("partner.invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="SET NULL"),
        nullable=True,
    )

    description = Column(Text, nullable=False)
    quantity = Column(Integer, nullable=False, server_default=text("1"))
    unit_price = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    amount = Column(Numeric(14, 2), nullable=False)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    invoice = relationship("Invoice", back_populates="items", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="chk_invoice_items_qty_nonneg"),
        CheckConstraint("unit_price >= 0", name="chk_invoice_items_unit_price_nonneg"),
        CheckConstraint("amount >= 0", name="chk_invoice_items_amount_nonneg"),
        CheckConstraint("sort_order >= 0", name="chk_invoice_items_sort_nonneg"),
        Index("idx_invoice_items_invoice_sort", "invoice_id", "sort_order"),
        Index("idx_invoice_items_project", "project_id"),
        {"schema": "partner"},
    )


# ========== partner.payouts ==========
class Payout(Base):
    __tablename__ = "payouts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    payout_number = Column(Text, nullable=False)

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(Text, nullable=False, server_default=text("'pending'"))  # pending/processing/paid/failed/canceled
    initiated_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    items = relationship("PayoutItem", back_populates="payout", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "payout_number", name="uq_payouts_partner_number"),
        CheckConstraint("total_amount >= 0", name="chk_payouts_total_nonneg"),
        CheckConstraint("period_end >= period_start", name="chk_payouts_period_valid"),
        Index("idx_payouts_partner_period", "partner_id", "period_start"),
        Index("idx_payouts_status", "status"),
        {"schema": "partner"},
    )


# ========== partner.payout_items ==========
class PayoutItem(Base):
    __tablename__ = "payout_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    payout_id = Column(
        BigInteger,
        ForeignKey("partner.payouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_id = Column(
        BigInteger,
        ForeignKey("partner.invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    amount = Column(Numeric(14, 2), nullable=False)
    fee_amount = Column(Numeric(14, 2), nullable=False, server_default=text("0"))
    net_amount = Column(Numeric(14, 2), nullable=False)
    notes = Column(Text, nullable=True)

    payout = relationship("Payout", back_populates="items", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("amount >= 0", name="chk_payout_items_amount_nonneg"),
        CheckConstraint("fee_amount >= 0", name="chk_payout_items_fee_nonneg"),
        CheckConstraint("net_amount >= 0", name="chk_payout_items_net_nonneg"),
        Index("idx_payout_items_payout", "payout_id"),
        Index("idx_payout_items_invoice", "invoice_id"),
        {"schema": "partner"},
    )


# ========== partner.fee_rates ==========
class FeeRate(Base):
    __tablename__ = "fee_rates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    fee_type = Column(Text, nullable=False)  # e.g. 'platform', 'processing'

    percentage = Column(Numeric(5, 2), nullable=True)     # 0~100
    flat_amount = Column(Numeric(14, 2), nullable=True)

    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("partner_id", "fee_type", "effective_from", name="uq_fee_rates_key"),
        CheckConstraint(
            "percentage IS NULL OR (percentage >= 0 AND percentage <= 100)",
            name="chk_fee_rates_pct_range",
        ),
        CheckConstraint("flat_amount IS NULL OR flat_amount >= 0", name="chk_fee_rates_flat_nonneg"),
        CheckConstraint(
            "(percentage IS NOT NULL) OR (flat_amount IS NOT NULL)",
            name="chk_fee_rates_one_of_pct_flat",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="chk_fee_rates_period_valid",
        ),
        Index("idx_fee_rates_partner_type", "partner_id", "fee_type"),
        {"schema": "partner"},
    )


# ========== partner.payout_accounts ==========
class PayoutAccount(Base):
    __tablename__ = "payout_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        nullable=False,
    )

    bank_name = Column(Text, nullable=False)
    account_number_encrypted = Column(Text, nullable=False)
    account_holder = Column(Text, nullable=False)
    routing_number = Column(Text, nullable=True)
    currency = Column(Text, nullable=False, server_default=text("'KRW'"))
    is_primary = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "uq_payout_accounts_partner_primary",
            "partner_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
        Index("idx_payout_accounts_partner", "partner_id"),
        {"schema": "partner"},
    )


# ========== partner.business_profiles ==========
class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    partner_id = Column(
        BigInteger,
        ForeignKey("partner.partners.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    business_registration_number = Column(Text, nullable=True)
    company_name = Column(Text, nullable=False)
    representative_name = Column(Text, nullable=False)
    address_line1 = Column(Text, nullable=False)
    address_line2 = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    state = Column(Text, nullable=True)
    postal_code = Column(Text, nullable=True)
    country = Column(Text, nullable=False)
    tax_email = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_business_profiles_country", "country"),
        {"schema": "partner"},
    )

