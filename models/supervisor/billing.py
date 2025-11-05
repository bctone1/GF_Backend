# models/billing.py
from sqlalchemy import (
    Column, BigInteger, String, Integer, DateTime, Date, Numeric, Text,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from models.base import Base


# ========== supervisor.transactions ==========
class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id = Column(
        BigInteger,
        ForeignKey("supervisor.plans.plan_id", ondelete="SET NULL"),
        nullable=True,
    )

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), nullable=False, server_default=text("'USD'"))

    status = Column(String(32), nullable=False)  # pending | succeeded | failed | refunded
    payment_method = Column(String(64), nullable=True)  # card | bank_transfer | invoice | etc
    transaction_type = Column(String(32), nullable=False, server_default=text("'subscription'"))  # subscription | usage | adjustment

    transacted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    invoice_url = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("amount >= 0", name="chk_transactions_amount_nonneg"),
        CheckConstraint(
            "status IN ('pending','succeeded','failed','refunded')",
            name="chk_transactions_status",
        ),
        CheckConstraint(
            "transaction_type IN ('subscription','usage','adjustment')",
            name="chk_transactions_type",
        ),
        Index("idx_transactions_org_time", "organization_id", "transacted_at"),
        Index("idx_transactions_status_time", "status", "transacted_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.invoices ==========
class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )

    billing_period_start = Column(Date, nullable=False)
    billing_period_end = Column(Date, nullable=False)

    total_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(32), nullable=False)  # draft | issued | paid | overdue | void

    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "billing_period_start", "billing_period_end",
            name="uq_invoices_org_period",
        ),
        CheckConstraint("total_amount >= 0", name="chk_invoices_total_nonneg"),
        CheckConstraint(
            "billing_period_end >= billing_period_start",
            name="chk_invoices_period_valid",
        ),
        CheckConstraint(
            "status IN ('draft','issued','paid','overdue','void')",
            name="chk_invoices_status",
        ),
        Index("idx_invoices_org_period", "organization_id", "billing_period_start"),
        Index("idx_invoices_status", "status"),
        {"schema": "supervisor"},
    )


# ========== supervisor.subscription_changes ==========
class SubscriptionChange(Base):
    __tablename__ = "subscription_changes"

    change_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organization_id = Column(
        BigInteger,
        ForeignKey("supervisor.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    old_plan_id = Column(
        BigInteger,
        ForeignKey("supervisor.plans.plan_id", ondelete="SET NULL"),
        nullable=True,
    )
    new_plan_id = Column(
        BigInteger,
        ForeignKey("supervisor.plans.plan_id", ondelete="SET NULL"),
        nullable=True,
    )

    effective_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String(255), nullable=True)
    changed_by = Column(BigInteger, nullable=True)  # FK 최소화

    __table_args__ = (
        Index("idx_subscription_changes_org_time", "organization_id", "effective_at"),
        {"schema": "supervisor"},
    )


# ========== supervisor.arpu_history ==========
# 주의: 애플리케이션에서 직접 INSERT 금지. ETL/잡이 적재.
class ArpuHistory(Base):
    __tablename__ = "arpu_history"

    record_id = Column(BigInteger, primary_key=True, autoincrement=True)
    period = Column(Date, nullable=False)                 # 보통 YYYY-MM-01
    arpu_value = Column(Numeric(12, 4), nullable=False)

    plan_id = Column(
        BigInteger,
        ForeignKey("supervisor.plans.plan_id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("arpu_value >= 0", name="chk_arpu_history_nonneg"),
        Index("idx_arpu_history_period", "period"),
        Index("idx_arpu_history_plan_period", "plan_id", "period"),
        {"schema": "supervisor"},
    )
